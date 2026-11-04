use zed_extension_api::{
    self as zed, serde_json, settings::LspSettings, Command, DebugAdapterBinary, DebugConfig,
    DebugRequest, DebugScenario, DebugTaskDefinition, LanguageServerId, Result,
    StartDebuggingRequestArguments, StartDebuggingRequestArgumentsRequest, TaskTemplate, Worktree,
};

const SERVER_NAME: &str = "renpy-language-server";
const ADAPTER_NAME: &str = "renpy";

/// Server versions the launcher is allowed to start. The extension and the
/// server are versioned together; widen this range only after testing.
const SERVER_REQUIREMENT: &str = "renpy-language-server>=0.2,<0.3";

struct RenpyExtension;

#[derive(Debug, PartialEq, Eq)]
struct ResolvedCommand {
    command: String,
    args: Vec<String>,
}

impl ResolvedCommand {
    fn new(command: impl Into<String>, args: Vec<String>) -> Self {
        Self {
            command: command.into(),
            args,
        }
    }

    fn into_command(self) -> Command {
        Command {
            command: self.command,
            args: self.args,
            env: Default::default(),
        }
    }
}

/// Pick a server command without touching the environment.
///
/// Resolution order:
/// 1. explicit path in Zed settings (`lsp.renpy-language-server.binary.path`)
/// 2. `renpy-language-server` on `PATH`
/// 3. `uvx --from <requirement> renpy-language-server`
/// 4. `uv tool run --from <requirement> renpy-language-server`
/// 5. `python3 -m renpy_language_server` / `python -m renpy_language_server`
fn resolve_command(
    settings_binary: Option<(String, Vec<String>)>,
    which: impl Fn(&str) -> Option<String>,
) -> Option<ResolvedCommand> {
    if let Some((path, args)) = settings_binary {
        return Some(ResolvedCommand::new(path, args));
    }

    if let Some(path) = which(SERVER_NAME) {
        return Some(ResolvedCommand::new(path, Vec::new()));
    }

    if let Some(path) = which("uvx") {
        return Some(ResolvedCommand::new(
            path,
            vec![
                "--from".to_string(),
                SERVER_REQUIREMENT.to_string(),
                SERVER_NAME.to_string(),
            ],
        ));
    }

    if let Some(path) = which("uv") {
        return Some(ResolvedCommand::new(
            path,
            vec![
                "tool".to_string(),
                "run".to_string(),
                "--from".to_string(),
                SERVER_REQUIREMENT.to_string(),
                SERVER_NAME.to_string(),
            ],
        ));
    }

    for python in ["python3", "python"] {
        if let Some(path) = which(python) {
            return Some(ResolvedCommand::new(
                path,
                vec!["-m".to_string(), "renpy_language_server".to_string()],
            ));
        }
    }

    None
}

/// The DAP request kind a launch configuration asks for. Only "launch" is
/// supported: attaching to an already-running game is not implemented yet.
fn request_kind(config: &serde_json::Value) -> Result<StartDebuggingRequestArgumentsRequest> {
    match config.get("request").and_then(|value| value.as_str()) {
        None | Some("launch") => Ok(StartDebuggingRequestArgumentsRequest::Launch),
        Some("attach") => Err(
            "attaching to a running Ren'Py game is not supported yet — use a \
             launch configuration"
                .to_string(),
        ),
        Some(other) => Err(format!(
            "unknown request kind '{other}' (expected \"launch\")"
        )),
    }
}

/// The debug configuration for one of the tasks in `languages/renpy/tasks.json`,
/// which mark themselves with `RENPY_ZED_TASK` ("run" or "warp"). The adapter
/// launches the game itself, so no build task is needed.
fn task_debug_config(task: &TaskTemplate) -> Option<serde_json::Value> {
    let kind = task
        .env
        .iter()
        .find(|(key, _)| key == "RENPY_ZED_TASK")?
        .1
        .as_str();
    match kind {
        "run" => Some(serde_json::json!({ "request": "launch" })),
        "warp" => Some(serde_json::json!({
            "request": "launch",
            "warp": "$ZED_FILE:$ZED_ROW"
        })),
        _ => None,
    }
}

impl RenpyExtension {
    fn resolved_server_command(&mut self, worktree: &Worktree) -> Result<ResolvedCommand> {
        let settings_binary = LspSettings::for_worktree(SERVER_NAME, worktree)
            .ok()
            .and_then(|settings| settings.binary)
            .and_then(|binary| {
                binary
                    .path
                    .map(|path| (path, binary.arguments.unwrap_or_default()))
            });

        resolve_command(settings_binary, |name| worktree.which(name)).ok_or_else(|| {
            format!(
                "Could not find a compatible '{SERVER_NAME}' server. \
                 Install it with `uv tool install 'renpy-language-server>=0.2,<0.3'` (Python 3.10+), \
                 or set `lsp.{SERVER_NAME}.binary.path` in Zed settings."
            )
        })
    }

    fn server_command(
        &mut self,
        _language_server_id: &LanguageServerId,
        worktree: &Worktree,
    ) -> Result<Command> {
        self.resolved_server_command(worktree)
            .map(ResolvedCommand::into_command)
    }
}

impl zed::Extension for RenpyExtension {
    fn new() -> Self {
        RenpyExtension
    }

    fn language_server_command(
        &mut self,
        language_server_id: &LanguageServerId,
        worktree: &Worktree,
    ) -> Result<Command> {
        self.server_command(language_server_id, worktree)
    }

    fn get_dap_binary(
        &mut self,
        adapter_name: String,
        config: DebugTaskDefinition,
        user_provided_debug_adapter_path: Option<String>,
        worktree: &Worktree,
    ) -> Result<DebugAdapterBinary, String> {
        if adapter_name != ADAPTER_NAME {
            return Err(format!("unknown debug adapter '{adapter_name}'"));
        }

        let command = match user_provided_debug_adapter_path {
            Some(path) if !path.trim().is_empty() => path,
            _ => self.resolved_server_command(worktree)?.command,
        };
        let configuration: serde_json::Value = serde_json::from_str(&config.config)
            .map_err(|err| format!("invalid debug configuration: {err}"))?;
        let request = request_kind(&configuration)?;

        Ok(DebugAdapterBinary {
            command: Some(command),
            arguments: vec!["dap".to_string()],
            envs: Vec::new(),
            cwd: Some(worktree.root_path()),
            connection: None,
            request_args: StartDebuggingRequestArguments {
                configuration: config.config,
                request,
            },
        })
    }

    fn dap_request_kind(
        &mut self,
        _adapter_name: String,
        config: serde_json::Value,
    ) -> Result<StartDebuggingRequestArgumentsRequest, String> {
        request_kind(&config)
    }

    /// Map the generic new-session modal (program/cwd/args/env) onto a Ren'Py
    /// launch configuration: for Ren'Py, "the program" is the project root.
    fn dap_config_to_scenario(&mut self, config: DebugConfig) -> Result<DebugScenario, String> {
        match config.request {
            DebugRequest::Launch(launch) => {
                let mut scenario = serde_json::json!({ "request": "launch" });
                if !launch.program.trim().is_empty() {
                    scenario["project"] = launch.program.into();
                } else if let Some(cwd) = launch.cwd {
                    scenario["project"] = cwd.into();
                }
                if !launch.args.is_empty() {
                    scenario["args"] = launch.args.into();
                }
                if !launch.envs.is_empty() {
                    scenario["env"] = launch
                        .envs
                        .into_iter()
                        .map(|(key, value)| (key, serde_json::Value::String(value)))
                        .collect::<serde_json::Map<String, serde_json::Value>>()
                        .into();
                }
                Ok(DebugScenario {
                    adapter: config.adapter,
                    label: config.label,
                    config: scenario.to_string(),
                    build: None,
                    tcp_connection: None,
                })
            }
            DebugRequest::Attach(_) => {
                Err("attaching to a running Ren'Py game is not supported yet".to_string())
            }
        }
    }

    /// Offer a "debug" variant beside the existing run tasks: the ▶ next to a
    /// label, "run from line" and "run game" start the same project through
    /// the debug adapter.
    fn dap_locator_create_scenario(
        &mut self,
        locator_name: String,
        build_task: TaskTemplate,
        resolved_label: String,
        _debug_adapter_name: String,
    ) -> Option<DebugScenario> {
        if locator_name != ADAPTER_NAME {
            return None;
        }
        let config = task_debug_config(&build_task)?;
        Some(DebugScenario {
            label: resolved_label.replacen("Ren'Py: run", "Ren'Py: debug", 1),
            adapter: ADAPTER_NAME.to_string(),
            config: config.to_string(),
            build: None,
            tcp_connection: None,
        })
    }
}

zed::register_extension!(RenpyExtension);

#[cfg(test)]
mod tests {
    use super::*;

    fn no_tools(_: &str) -> Option<String> {
        None
    }

    fn all_tools(name: &str) -> Option<String> {
        Some(format!("/usr/bin/{name}"))
    }

    fn only(names: &'static [&'static str]) -> impl Fn(&str) -> Option<String> {
        move |name| names.contains(&name).then(|| format!("/usr/bin/{name}"))
    }

    #[test]
    fn settings_path_wins() {
        let resolved = resolve_command(
            Some((
                "/custom/renpy-language-server".into(),
                vec!["--stdio".into()],
            )),
            all_tools,
        )
        .expect("settings path should resolve");

        assert_eq!(resolved.command, "/custom/renpy-language-server");
        assert_eq!(resolved.args, ["--stdio"]);
    }

    #[test]
    fn path_binary_beats_uvx() {
        let resolved = resolve_command(None, all_tools).expect("PATH should resolve");

        assert_eq!(resolved.command, "/usr/bin/renpy-language-server");
        assert!(resolved.args.is_empty());
    }

    #[test]
    fn uvx_is_pinned() {
        let resolved =
            resolve_command(None, only(&["uvx", "python3"])).expect("uvx should resolve");

        assert_eq!(resolved.command, "/usr/bin/uvx");
        assert_eq!(resolved.args, ["--from", SERVER_REQUIREMENT, SERVER_NAME]);
    }

    #[test]
    fn uv_is_a_fallback() {
        let resolved = resolve_command(None, only(&["uv", "python3"])).expect("uv should resolve");

        assert_eq!(resolved.command, "/usr/bin/uv");
        assert_eq!(
            resolved.args,
            ["tool", "run", "--from", SERVER_REQUIREMENT, SERVER_NAME]
        );
    }

    #[test]
    fn python_module_is_the_last_fallback() {
        let resolved = resolve_command(None, only(&["python"])).expect("python should resolve");

        assert_eq!(resolved.command, "/usr/bin/python");
        assert_eq!(resolved.args, ["-m", "renpy_language_server"]);
    }

    #[test]
    fn missing_server_is_an_error() {
        assert_eq!(resolve_command(None, no_tools), None);
    }

    #[test]
    fn debug_request_kind_is_launch_only() {
        assert_eq!(
            request_kind(&serde_json::json!({})),
            Ok(StartDebuggingRequestArgumentsRequest::Launch)
        );
        assert_eq!(
            request_kind(&serde_json::json!({ "request": "launch" })),
            Ok(StartDebuggingRequestArgumentsRequest::Launch)
        );
        assert!(request_kind(&serde_json::json!({ "request": "attach" })).is_err());
        assert!(request_kind(&serde_json::json!({ "request": "other" })).is_err());
    }

    fn task_template(kind: Option<&str>) -> TaskTemplate {
        TaskTemplate {
            label: "Ren'Py: run game".to_string(),
            command: "sh".to_string(),
            args: Vec::new(),
            env: kind
                .map(|kind| vec![("RENPY_ZED_TASK".to_string(), kind.to_string())])
                .unwrap_or_default(),
            cwd: None,
        }
    }

    #[test]
    fn run_tasks_become_launch_scenarios() {
        let run = task_debug_config(&task_template(Some("run"))).unwrap();
        assert_eq!(run["request"], "launch");
        assert!(run.get("warp").is_none());

        let warp = task_debug_config(&task_template(Some("warp"))).unwrap();
        assert_eq!(warp["warp"], "$ZED_FILE:$ZED_ROW");

        assert!(task_debug_config(&task_template(Some("lint"))).is_none());
        assert!(task_debug_config(&task_template(None)).is_none());
    }
}
