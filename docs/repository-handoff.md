# Private repository handoff

Prepared 3 October 2026 UTC. A remote repository has not been created, uploaded or shared. No destination account or supervisor invitation is recorded. This guide prepares the handoff without claiming that access already exists.

## Decide what to share before annotation

The complete archive preserves all research evidence, including procedurally reserved test material and author labels. A private repository is not a blinding mechanism. Someone with access can read those files, including files named .sealed.

Before the independent student pass is resolved, share a **code-review copy** that excludes the Experiment 2 language-bank directories, caches and parser predictions. The separate annotation handoff supplies the material required for the student pass. The supervisor can receive the complete evidence archive separately with a clear note about the reserved material. Keep the original archive and its fingerprint intact.

Do not delete or rewrite any frozen file to create a simpler repository. Make a separate sharing copy and keep an inventory of included and excluded paths. The full research archive remains the authoritative evidence package. A partial code-review repository cannot pass the full-archive verifier and must be labelled accordingly.

## Suggested first code-review upload

Create a new private repository under the student's chosen account. Add a description such as: "COMP 9500 offline controllability study. Experiment 1 complete; Experiment 2 reserved evaluation pending."

Use the separate COMP9500-Code-Review-Copy.zip when supplied. It contains the implementation and dependency files, frontend source and build, test source, selected instructions, current paper, current BCIT slides and supervision documents. Its sharing-manifest.json lists included and excluded source files with SHA-256 hashes. All results folders, data, Experiment 2 language banks, caches, parser predictions and original source evidence are excluded. Dependency/VCS directories are excluded without traversal and listed separately. Keep research evidence in the separately fingerprinted full archive.

This copy is not blind-annotator material: it contains the parser implementation and development summaries. The student must not read it during the independent annotation pass. It is also not the executable full evidence package. Some isolated synthetic tests may run, but full tests, checkpoint inference, experiment replay and archive/release verification require the authoritative archive. The copy's README-CODE-REVIEW.md takes precedence over installation instructions referring to omitted evidence.

To rebuild the copy after the current paper and slides are final, run the following from the authoritative package. This packages files and writes a manifest; it does not execute experiments, create a Git repository or upload anything. The script refuses to overwrite an existing output.

```bash
python scripts/prepare_code_review_copy.py --output outgoing/COMP9500-Code-Review-Copy.zip
```

Before committing, inspect the staged file list and look for credentials, local configuration, generated environments, unexpected archives and reserved materials. The existing .gitignore excludes common environment and cache files; it does not certify that all sensitive or reserved files are excluded. Do not use a blind "add everything" command.

The following commands are a local preparation example. They have not been run for this handoff and contain no remote destination:

```bash
git init -b main
git status --short
git add --dry-run README.md START-HERE.md pyproject.toml feedctrl tests scripts web
```

Review that preview and select the approved files explicitly before committing. The code-review copy should have its own short README explaining exclusions. Do not execute the commands against the authoritative evidence archive without understanding the staged paths.

Once the repository is created, add the confirmed remote URL, push the reviewed commit and invite the supervisor's confirmed account. Record the URL, commit hash, visibility, invitation time and confirmation of access in the weekly update. No account, URL or completed invitation is invented in this package.

## Keep the evidence reproducible

Preserve the release ZIP, its SHA-256 fingerprint and the inventory supplied with the handoff. Record the exact package fingerprint in the repository README. Use separate directories for any rerun, including logs, versions, timestamps and outputs; never overwrite Experiment 1 evidence.

After the annotation and reserved evaluation process is complete, review whether the full evidence should be added to the private repository or distributed as a release archive. Check publisher terms and NOTICE.md before a wider public release. Do not upload Ollama or Llama weights, full upstream downloads, credentials or machine-specific secrets.

For each weekly update, link the actual commit and evidence file corresponding to completed work. A commit records a change; it is not itself proof that the student authored every line, executed a test or spent a claimed number of hours.

## Completion record

- Repository URL: pending.
- Student account and owner: pending.
- Visibility: private is the intended setting; not yet created.
- First reviewed commit: pending.
- Supervisor account and invitation: pending.
- Supervisor access confirmed: pending.
- Authoritative archive fingerprint recorded: pending final package.
- Annotation exposure review: pending.
