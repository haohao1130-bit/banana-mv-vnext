# Local guide provisioning

Windows `python -m banana_mv.server` startup now reuses an existing official
Ref2VA guide, or attempts one download from the official MiniMaxAI repository
with an eight-second request timeout. It caches under BANANA_DATA/guides when
no repository guide exists. Existing readable config.guides.ref and
BANANA_REF_GUIDE paths are respected. Existing files are never replaced.
Download errors warn and do not prevent the UI from starting. Other platforms
keep their current startup behavior; the Colab installer is unchanged.

New author attempts save preproduction/whole_film_guide.json with the effective
path, available flag, file byte count and SHA-256, alongside the actual system
commission. An unavailable guide is still reported by the existing warning path.
This records actual availability, not just an intention to load the guide.

Validation: 358 offline Python tests plus frontend and asset checks passed.
Provisioning tests cover success, cache reuse, offline/invalid responses and
existing local configuration. A real request from the agent workspace received
HTTP 403, so live download success on the user's Windows network is NOT claimed.
After updating, verify the startup result and new job's guide record; do not use
a guide-missing run as the guide-loaded control arm of an author A/B experiment.

This patch addresses the environment baseline only. Reference/Subject mapping,
no-op repair semantics and author prompt A/B remain separate follow-up work.
