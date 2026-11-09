# Banana MV VNext

Independent whole-song preproduction prototype. The legacy MV and Film repositories are unchanged.

Flow: one complete screenplay → one camera-only plan → deterministic six-section H3 prompt compilation → sealed project. No per-render story rewrite.

## Current delivery

- Standard-library Python core and offline replay CLI; no model or GPU dependency.
- Exact 24fps source timeline, stable ordered reference slots and explicit source-vocal bindings.
- Camera fields are enums. Added narrative keys, omitted clips and invalid cut timing fail closed.
- Source song, reference order, screenplay, camera and prompts are hashed. `inspect` also recompiles prompts against the authoritative plan.
- Existing project directories are preserved. Invalid responses retain raw diagnostics and never create `ready.json`.

This is preproduction infrastructure, not a usable Colab generation app yet. It does not claim real 9B/H3 quality or official parser acceptance. The six-section format follows the existing MV integration conventions and still requires native-node validation.

## Offline use

```
python -m unittest discover -s tests -v
python -m mvnext prepare --project projects/demo --story story.txt --song song.wav --song-frames 720 --picture actor.png --screenplay screenplay.json --camera camera.json
python -m mvnext inspect --project projects/demo --song song.wav --picture actor.png
```

The CLI replays supplied model-response JSON files; it does not contact a model. `song-frames` must eventually come from verified decoded audio duration. Currently the caller supplies it. Source assets are hashed as bytes; valid image/audio decoding is pending.

## Screenplay contract

Root: `title`, `subjects`, `clips` only.

- Subject: `id` positive integer, `name`, `picture` 1-based upload slot, `appearance`, `voice` positive source-voice ID or null. This first slice requires referenced cast; original supporting cast and multiple roles per image need a later explicit contract.
- Clip: sequential 0-based `index`, contiguous `start_frame`, `frames`, `opening`, `outgoing`, `beats`.
- Beat: globally unique `id`, strictly increasing local `at_frame`, `action`, `singer` subject ID or null. Source lyrics are not generated dialogue.
- All frames sum exactly to source song frames. Clips are at most 345 delivered frames; nonfinal windows at least 124. Render padding and five-frame guide lengths are not implemented here.
- Narrative fields are single-line text and cannot inject H3 tags or section/shot syntax. The original user story may contain multiple lines.

Camera root: `clips`. Each clip has `index`, `shots`; each shot has `at_frame`, `size`, `angle`, `motion`. First shot starts at zero. See `CAMERA` in `mvnext/pipeline.py` for supported enums. No narrative fallback or silent timing repair is performed.

The model interface is `model(role, payload)`. A live adapter must supply the full schema, original story, verified timing, SRT/vocal assignments and actual image references. This prototype's payloads and replay interface are not a production 9B prompt yet.

## Next acceptance gates

1. Human screenplay approval plus persistent revision identity; structural validation does not prove faithful story interpretation.
2. Live 9B adapter with full schemas, source timing/SRT, vocal roles and picture inputs. Bound retries while retaining raw attempts.
3. Verify actual native H3 graph, source-audio lock and legal render/prefix frames before GPU work.
4. A 30-second real sample covering singing and action, cross-clip continuity, audio sync and interrupt/resume.
5. Frontend, retake versions and explicit adoption. Rendering must consume sealed prompts without writer calls.

## Source review

Design reviewed against Film VNext `7df237c5f2a74ff6de0465a67142fe5f487c6b73` and legacy MV official-format changes `615c104d40e7e9508ca719e7d479461b0832270e` / `ff3010216fccbca8d4d41362b8d15b3f48c95288`. No runtime code or private media was copied. Hashes detect accidental changes, not hostile replacement of an entire manifest.
