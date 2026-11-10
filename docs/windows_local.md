# Windows Desktop: recipe-only local testing

Keep the existing Comfy Desktop local instance running. No node graph needs to be
assembled manually: Banana submits its own TextGenerate workflow to the local API.
Install the W4A8 9B Ref2VA rewriter in an active `models/text_encoders` directory
and restart the instance. H3 video weights, video encoders, VAEs and motion LoRAs
are not required when selecting **先搓丹方** (prepare recipe).

From the cloned repository in a normal PowerShell:

```powershell
git pull --ff-only
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\start_local.ps1
```

The process-scoped execution-policy override does not change machine settings.
The launcher uses `Documents\ComfyUI\.venv\Scripts\python.exe`, the active input
directory `Documents\ComfyUI\input` and the observed Desktop API at localhost:8000.
Pass `-ComfyRoot`, `-PythonPath` or `-ComfyUrl` if your installation differs. It
reuses the installed Python without installing packages or changing ComfyUI.
FFmpeg **and ffprobe** must be on PATH (they are used to read the uploaded audio).
If absent, install them, e.g. `winget install --id Gyan.FFmpeg -e`, then open a new
PowerShell so it sees the updated PATH. The launcher does not install software.

Open http://127.0.0.1:8190. Upload the original references/song, optionally SRT,
leave local 9B enabled and select **先搓丹方**. For the initial local test disable
music-structure analysis: that optional service currently uses the Colab-managed
separate environment. Basic audio analysis remains available. Keep the launcher
terminal open; Ctrl+C stops the Banana frontend, not ComfyUI.

Local tasks live in `%LOCALAPPDATA%\BananaMVVNext`, outside the Git checkout.
Existing config fields are preserved; only the selected Comfy URL/input directory
are updated. No GitHub token, upload or GPU cloud subscription is needed for this
local connection. Git updates code only, not songs, images or model weights.

This launcher has not been executed on a real Windows/5070 machine by the project
maintainer. It is a setup helper, not a guarantee that a five-minute model output
fits GPU memory. Start by preparing the current one-minute song and record the
model generation metrics before increasing duration.
