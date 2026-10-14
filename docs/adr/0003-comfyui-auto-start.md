# The image skill starts its own renderer when down

The Wolf serves a non-technical human who must never know what ComfyUI is, so `qwen_image_skill` launches the local renderer itself (`_ensure_comfy`: port-check → detached start → wait) when a render is requested and `:8188` is silent, instead of returning "install/run it" as homework.

## Consequences

- A render request can pause ~2 minutes for cold start before denoising begins; the caller sees heartbeats, not an error.
- If auto-start fails (venv missing), the skill returns runner-pending with a plain-Arabic message — the only case the human ever hears about the renderer.
