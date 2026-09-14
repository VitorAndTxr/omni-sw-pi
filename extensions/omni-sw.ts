/**
 * pi-omni-sw — pi extension entry point.
 *
 * Wires the bundled Omni-SW agency CLI and agents into pi:
 *  - writes a path manifest (~/.pi/agent/omni-sw.json) so skills resolve the CLI reliably
 *  - registers the `omni_sw_cli` tool (deterministic SDLC operations)
 *  - registers the `/omni-sw` command to kick off the TDD SDLC
 *  - warns when Python 3 is unavailable
 */

import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { spawn, spawnSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const EXT_DIR = dirname(fileURLToPath(import.meta.url));
const PKG_ROOT = dirname(EXT_DIR);
const SHARED_DIR = join(PKG_ROOT, "skills", "omni-sw-shared");
const CLI = join(SHARED_DIR, "scripts", "agency_cli.py");
const BACKLOG_SCRIPT = join(PKG_ROOT, "skills", "omni-sw-backlog", "scripts", "backlog_manager.py");
const MODELS_JSON = join(SHARED_DIR, "models.json");
const MANIFEST_DIR = join(homedir(), ".pi", "agent");
const MANIFEST = join(MANIFEST_DIR, "omni-sw.json");

/** Top-level agency_cli subcommands the tool is allowed to run. */
const ALLOWED_SUBCOMMANDS = new Set([
	"init", "setup", "phase", "gate", "agent", "backlog", "scan",
	"diagram", "tokens", "report", "state", "decision", "pipeline",
	"metrics", "notify",
]);

function detectPython(): string | null {
	const candidates = process.platform === "win32"
		? ["python", "py", "python3"]
		: ["python3", "python"];
	for (const candidate of candidates) {
		try {
			const result = spawnSync(candidate, ["--version"], {
				encoding: "utf8",
				timeout: 5000,
				windowsHide: true,
			});
			if (result.status === 0) return candidate;
		} catch {
			// try the next candidate
		}
	}
	return null;
}

function writeManifest(python: string | null): void {
	try {
		mkdirSync(MANIFEST_DIR, { recursive: true });
		writeFileSync(
			MANIFEST,
			JSON.stringify(
				{
					package: "pi-omni-sw",
					root: PKG_ROOT,
					cli: CLI,
					backlog_script: BACKLOG_SCRIPT,
					models: MODELS_JSON,
					python,
					updated_at: new Date().toISOString(),
				},
				null,
				2,
			),
			"utf8",
		);
	} catch {
		// best effort — skills still have a Glob fallback
	}
}

function runCli(
	python: string,
	args: string[],
	cwd: string,
	signal: AbortSignal | undefined,
): Promise<{ text: string; exitCode: number | null; spawnError?: string }> {
	return new Promise((resolve) => {
		const child = spawn(python, [CLI, ...args], {
			cwd,
			env: { ...process.env, OMNI_SW_ROOT: PKG_ROOT, OMNI_SW_CLI: CLI },
			windowsHide: true,
		});
		let stdout = "";
		let stderr = "";
		const onAbort = () => child.kill();
		signal?.addEventListener("abort", onAbort);
		child.stdout?.on("data", (chunk) => { stdout += chunk.toString(); });
		child.stderr?.on("data", (chunk) => { stderr += chunk.toString(); });
		child.on("error", (error) => {
			signal?.removeEventListener("abort", onAbort);
			resolve({ text: "", exitCode: null, spawnError: error.message });
		});
		child.on("close", (code) => {
			signal?.removeEventListener("abort", onAbort);
			const text = [stdout.trim(), stderr.trim()].filter(Boolean).join("\n");
			resolve({ text: text || `(no output, exit ${code})`, exitCode: code });
		});
	});
}

export default function omniSwExtension(pi: ExtensionAPI) {
	let python = detectPython();
	writeManifest(python);

	pi.on("session_start", (_event, ctx) => {
		python = detectPython();
		writeManifest(python);
		if (!python) {
			ctx.ui.notify(
				"Omni-SW: Python 3 not found on PATH. Install Python 3.10+ to use the agency CLI.",
				"warning",
			);
		}
	});

	pi.registerTool({
		name: "omni_sw_cli",
		label: "Omni-SW CLI",
		description:
			"Run the bundled Omni-SW agency CLI for deterministic SDLC operations: init, setup, phase, gate, agent, backlog, state, pipeline, metrics, report, decision, notify, scan, diagram, tokens.",
		promptSnippet: "Run deterministic Omni-SW SDLC operations (phases, gates, backlog, state)",
		promptGuidelines: [
			"Use omni_sw_cli for Omni-SW agency operations instead of reconstructing agency_cli.py paths in bash.",
		],
		parameters: Type.Object({
			args: Type.Array(Type.String(), {
				description:
					"CLI arguments, e.g. ['phase','prepare','--phase','plan','--project-root','/path']",
			}),
			cwd: Type.Optional(
				Type.String({ description: "Working directory (defaults to the session cwd)" }),
			),
		}),
		async execute(
			_toolCallId: string,
			params: { args: string[]; cwd?: string },
			signal: AbortSignal | undefined,
			_onUpdate: unknown,
			ctx: ExtensionContext,
		) {
			if (!python) python = detectPython();
			if (!python) {
				return {
					content: [{ type: "text" as const, text: "Omni-SW: Python 3 was not found on PATH." }],
					details: { exitCode: null },
					isError: true,
				};
			}
			const [subcommand] = params.args;
			if (!subcommand || !ALLOWED_SUBCOMMANDS.has(subcommand)) {
				return {
					content: [
						{
							type: "text" as const,
							text: `Blocked: the first argument must be one of: ${[...ALLOWED_SUBCOMMANDS].join(", ")}`,
						},
					],
					details: { exitCode: null },
					isError: true,
				};
			}
			const result = await runCli(python, params.args, params.cwd ?? ctx.cwd, signal);
			if (result.spawnError) {
				return {
					content: [{ type: "text" as const, text: `Failed to launch ${python}: ${result.spawnError}` }],
					details: { exitCode: null },
					isError: true,
				};
			}
			return {
				content: [{ type: "text" as const, text: result.text }],
				details: { exitCode: result.exitCode },
				isError: result.exitCode !== 0,
			};
		},
	});

	pi.registerCommand("omni-sw", {
		description: "Start the Omni-SW TDD SDLC for an objective: /omni-sw <objective>. Use /omni-sw status for paths.",
		handler: async (args, ctx) => {
			const objective = args.trim();
			if (!objective || objective === "status" || objective === "info") {
				ctx.ui.notify(
					[
						`package: ${PKG_ROOT}`,
						`cli: ${CLI}`,
						`python: ${python ?? "NOT FOUND"}`,
						`manifest: ${MANIFEST}`,
					].join("\n"),
					python ? "info" : "warning",
				);
				return;
			}
			if (!python) {
				ctx.ui.notify("Omni-SW: Python 3 is required. Install Python 3.10+ and restart pi.", "error");
				return;
			}
			pi.sendUserMessage(`/skill:omni-sw-orchestrator ${JSON.stringify(objective)}`);
		},
	});
}
