# Multimodal Capture Phase 1 Design

## Purpose

Add consent-bound, read-only multimodal source ingestion as digital-body perception.

## Modalities

- `text_attachment`
- `image_file_observation`
- `audio_file_observation`
- `screen_snapshot_file_observation`
- `browser_capture_ref_observation`

## Source Contract

Each source normalizes into a source artifact with `source_id`, `modality`, `source_role`, `consent_scope`, `capture_method`, `artifact_ref`, `payload_digest`, `trust_tier`, `status`, `block_reasons`, and `writeback_ready=false`.

Allowed capture methods are `operator_attached_file`, `saved_source_ref_capture`, and `browser_runtime_capture_ref`.

## Explicit Blocks

- live microphone recording
- live camera capture
- background screen recording
- secret capture
- emotion inference from voice alone
- identity claims from image/audio alone

## Completion Gate

`python evals/run_multimodal_capture_audit.py` must report `multimodal_capture_phase1_ready`.
