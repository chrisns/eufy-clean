# S1 Pro P2P review and validation

Review date: 2026-10-11. Verified hardware: Eufy S1 Pro, model T2080A,
firmware 7.0.168/7.0.170, local Tuya 3.3. Other models retain their existing
MQTT, scalar and legacy command paths; their camera behavior is not verified.
The protocol details are in [P2P_MAP_CHANNEL.md](P2P_MAP_CHANNEL.md).

## Evidence and limits

| Check | Result |
| --- | --- |
| Local camera, 60-second attempt | 800x600 H.265 at 10 fps; 3,521 RTP packets, no sequence gaps or decoder error lines; decoded-frame updates continued to 59.98 seconds |
| HA camera, 45-second attempt | 219 MJPEG frames, 218 distinct; 44.81-second arrival span; largest gap 1.30 seconds |
| HA manual drive, separate early attempt | Two three-second left turns visibly rotated the camera view; mean grayscale difference 64.877 |
| Mode gating | Camera unavailable before manual mode and after leaving it; viewing does not change mode |
| Reviewed transport, fresh live map session | Seven stream objects, eight rooms and a pose decoded with PUSH tag verification and strict CBC padding; 10,127 decrypted bytes |
| Automated validation | 721 pytest tests passed; all required pre-commit hooks passed |

The 45-second camera attempt's late turn produced almost identical snapshots.
It is evidence for sustained video, not for movement. The separate early drive
attempt provides movement evidence. Neither snapshot differences nor historical
Tuya write acknowledgements alone prove navigation accuracy.

Stationary manual mode ended after about a minute in earlier attempts. Viewing
never renews it, starts cleaning, or enables the physical camera switch. Manual
movement requires mode 6; brake is allowed outside that mode. The robot's camera
is H.265 at about 10 fps; HA's MJPEG output is limited to 5 fps by its 0.2-second
frame interval. The map and camera share one P2P slot, so the map pauses while
video owns the slot and refreshes when video releases it.

A standard return-to-base was not confirmed after more than five minutes in the
final robot test. The search was stopped; HA confirmed idle, error 0, manual mode
off and camera unavailable. No manual docking is attempted or implied by the
camera evidence.

## Findings fixed in this review

- Sorted the integration manifest and removed Pillow from its requirements;
  Home Assistant already supplies Pillow and hassfest rejects duplicate core
  dependencies.
- Removed the five-variant, two-pass camera-start ladder and its diagnostics.
  Production sends the proven channel-0 HD sequence once, with a fixed startup
  timeout. The abandoned candidates are recorded below, not shipped as fallbacks.
- Removed locally generated P2P identities. A malformed cloud-issued session is
  rejected; it must not silently leave the reserved identity unused. Validation
  precedes launching ffmpeg, preventing a decoder leak on malformed config.
- Reject expired JPEGs and images after the camera switch or manual mode is off.
  Clear previous-session images when a new session starts. Watch decoded frames,
  not packet arrival, to detect a frozen decoder.
- Keep the local Tuya socket lock while a cancelled write finishes in its
  executor thread, preventing a brake/receiver/disconnect race.
- Await cancelled decoder/session tasks before releasing their P2P slot; guard
  delayed control startup after session closure. Restore cooldown state on exit.
- Make map refusal/quick-failure cooldowns uninterruptible by activity changes.
- Verify inbound KCP PUSH HMACs and CBC padding. Tag outbound window replies as
  well as PUSHes and ACKs. Device ACK/window records are untagged on this path.
- Enforce LZ4 output sizes, truncation and backreference validity; cap the first
  path snapshot as well as subsequent increments.
- Clear geometry, rooms, targets and motion from the previous map before a
  new map is assembled; do not expose its old image under the new room list.
- Stop drawing an idle, off-dock P2P robot at the dock. Use its reported pose;
  dock placement requires docked activity or charging.
- Reject invalid/non-finite drive durations, require manual mode before movement,
  reject overlapping movement runs, and let brake interrupt the current run.
- Remove unused P2P room/path constants, the KCP handler setter/timestamp, unused
  obstacle metadata/goto-target state, and an unused overlay option. Retain
  supported transport fallbacks and bundled protobuf schemas.

## Historical experiments retained only as notes

The startup labels in the investigation were `b`, `c`, `a`, `d`, `e`.
`b` selects HD using IOCtrl command 9, channel 0, value 4, then starts with
command 6 operations 0 and 4. It is the only sequence retained in production.
`c` repeated that sequence on channel 1; `a`/`d` used operation 3 on channels
0/1; `e` tried operations 1/2 on channel 0. They have no positive live evidence.
SD clarity value 2 produced traffic but lost periodic keyframes on this robot.
Untagged outgoing ACKs caused stalls/retransmissions. A separate WebRTC video
SDP was unnecessary: the verified video arrives on the application KCP channel.

The DP 181 passEn request with an extra protobuf wrapper returned success while
leaving passEn false. The corrected nesting is documented with the active wire
format. Legacy DP 155 RemoteCtrl writes were acknowledged but did not move this
S1 Pro; its V2 normal-direction envelope did. Camera frames were originally
obtained without a fault: a fault is not a prerequisite for the camera. Manual
control is the confirmed prerequisite used by the integration.

Tuya RTP byte 0 may be 0xa8 although the actual header is always 12 bytes on this
path. Treating its padding/CSRC bits as standard RTP moves the payload offset and
breaks decoding. Keep this device-specific parsing behavior. RTP sequence gaps
reset an in-progress H.265 fragment.

## PR ancestry and delivery

The sanitization of test fixtures rewrote upstream ancestor hashes. The old PR
merge-base therefore showed the integration rewrite and false conflicts. The
sanitized equivalent of upstream `baeb32c` was `1799997`: their runtime trees
were identical and only two synthetic test-fixture files differed. A normal
merge retaining the feature tree restored the actual upstream base as an
ancestor. No force push or reintroduction of private fixtures was needed.

Upstream PR workflows require maintainer approval for this contributor. The fork
HACS check also flags repository metadata: issues are disabled and topics are
missing on the fork; GitHub cannot identify the license on either repository
(`NOASSERTION`). These are separate from the passing integration manifest and
HACS metadata checks; the existing license is not changed by this PR.

The test workflow also supports explicit runs on the fork. Dependency install
failures now stop the job. The clean runner exposed a missing development
dependency, `voluptuous-serialize`, used by the configuration-form serialization
regressions; it is declared in both development dependency lists. The CI runner
installs FFmpeg so the generated H.265-to-JPEG test runs instead of being skipped.

The HA camera and movement evidence was obtained before this maintenance review.
The reviewed transport received an additional live map check; the camera startup
burst retains the exact proven HD packet bytes. The maintenance changes are in
the PR and local checkout. The running HA process retains the previously verified
build until its next restart; no further full HA restart was needed for this review.

## Existing captures

The images are unaltered captures, published with the owner's permission. The
HA dashboard and map are from the earlier map work; the robot photos are from
the successful HA turn test. They are demonstrations, not generated fixtures.

- [HA dashboard](screenshots/dashboard.jpg)
- [Rendered HA map](screenshots/map.png)
- [Robot before the turn](screenshots/robot-before.jpg)
- [Robot after the turn](screenshots/robot-after.jpg)
