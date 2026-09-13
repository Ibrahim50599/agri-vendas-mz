---
name: Gemini Vision compatibility
description: Compatibility rule for Gemini image-analysis model identifiers.
---

The configured Gemini API account may not expose older model IDs such as `gemini-1.5-flash`; image analysis requires a model currently listed with `generateContent`, such as `gemini-2.5-flash`.

**Why:** The image endpoint can receive a valid upload and still fail with a 404 when the model identifier is no longer available for the account's API version.

**How to apply:** When image analysis returns a model-not-found error, list the account's available models before changing upload or camera code, then select a listed Flash model that supports `generateContent`. Keep a lighter listed Flash model as a fallback for temporary 503 capacity errors.