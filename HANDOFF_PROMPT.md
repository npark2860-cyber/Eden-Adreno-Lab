# Handoff Prompt — Eden Adreno X1 Uniform cache A/B

Use this prompt when continuing the work in a new tab.

---

Eden Windows ARM64 / Snapdragon X / Adreno X1-85 구동분석 작업을 이어간다.

GitHub 저장소 `npark2860-cyber/Eden-Adreno-Lab`에서 현재 실험 브랜치 `exp/x1-uniform-cache-ab`의 실제 HEAD와 Actions 상태를 먼저 확인하고, 다음 문서를 기준 상태로 읽어라:

1. `CURRENT_HANDOFF.md`
2. `DEBUG_HISTORY.md`
3. `LAB_BOOTSTRAP.md`
4. `NEXT_ACTION_UNIFORM_CACHE_AB.md`
5. `HANDOFF_PROMPT.md`

이전 대화를 추측해서 복원하지 말고 위 문서와 실제 GitHub 상태를 source of truth로 삼아라.

고정 Eden baseline은 절대 변경하지 마라:

`eden-emulator/mirror`
`dc95cd09eea9749250fe31a3072684d341d19417`

이미 확정된 사실을 유지하라:

- alias direct copy 경로와 `RequestOutsideRenderPassOperationContext -> vkCmdCopyImage`는 필요한 동작이며 단순 제거 대상이 아니다.
- alias 반복은 동일 region이더라도 source `modification_tick`이 매번 전진했고 same-state candidate가 0이므로 trivial alias dedupe는 닫혔다.
- exact dc95 Vulkan은 `HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS = false`다.
- classic cached Uniform path는 `SynchronizeBuffer()`를 통해 clean range면 physical upload 없이 끝날 수 있다.
- adaptive small-Uniform fast path는 payload reuse가 아니라 mapped staging re-stream이다.
- Uniform stream/reuse 런타임에서 gameplay fast path는 사실상 전부 `fastSkip`이었고 `fastAlignment=0`이었다.
- classic cached path는 대부분 clean이었다.
- payload fingerprint 런타임에서 sampled repeated Uniform key의 97%+가 동일 fingerprint였고 same-frame repeat는 99%+ 동일 fingerprint였다.
- 따라서 이번 실험은 custom dedupe/reuse가 아니라 기존 classic cached path를 사용하는 policy A/B다.

`exp/x1-uniform-cache-ab`의 정적 준비는 이미 완료되어 있다. 다시 구현하지 마라.

추가된 핵심 파일:

- `tools/adreno_lab/transplant_dc95_uniform_cache_ab.py`
- `.github/workflows/build-dc95-x1-uniform-cache-ab.yml`

구현 의미:

- checkbox: `X1 A/B: Disable Adaptive Uniform Fast Stream`
- default OFF
- Qualcomm proprietary Vulkan에서만 활성
- OFF: 기존 payload-fingerprint 동작 보존
- ON: adaptive `fastSkip`만 mapped-stream 선택에서 제외하고 기존 classic cached `SynchronizeBuffer()` path로 fall-through
- `needs_alignment_stream`은 그대로 fast mapped streaming을 강제
- 설정값은 `BufferCacheRuntime` 생성 시 Qualcomm 여부와 함께 한 번만 확정하여 per-Uniform 설정 조회를 넣지 않음

건드리지 않은 범위:

- scheduler
- alias copy
- barrier / render-pass request
- dirty-state semantics
- staging / descriptor lifetime
- persistent Uniform binding
- previous staging allocation reuse / payload dedupe
- Vertex / Index / Storage 등 non-Uniform 경로

새 workflow는 `workflow_dispatch` 전용이며, 정적 준비 이후 아직 Actions 실행은 0회다.

다음 행동은 **빌드 승인을 기다리는 것**이다. 사용자의 fresh explicit authorization 없이는 ARM64 GitHub Actions를 절대 시작하거나 재실행하지 마라. 한 번의 승인 = 정확히 한 번의 build attempt다.

현재 최신 성공 runtime 기준 빌드는 payload diagnostic이다:

- workflow `Build dc95 X1 Uniform Payload Fingerprint`
- run `33040377420`
- job `98412364840`
- attempt 1
- build HEAD `9f1a916c7eaa72f3921cfa49233756dbbba5c3d9`
- artifact `Eden-dc95-X1-uniform-payload-fingerprint`
- artifact id `9634160587`
- SHA-256 `de68710492c8c221a8936cef97bb6d876dd44f409cd2d75074cee18bcab6106f`

새 탭에서는 먼저 실제 `exp/x1-uniform-cache-ab` HEAD와 Actions 0회 상태가 문서와 맞는지 확인한 뒤, 사용자가 빌드를 명시적으로 승인한 경우에만 `Build dc95 X1 Uniform Cache AB`를 정확히 1회 실행하라.

빌드 또는 런타임 결과가 생기면 `DEBUG_HISTORY.md`에 누적하고 `CURRENT_HANDOFF.md`를 최신 상태로 갱신하라.
