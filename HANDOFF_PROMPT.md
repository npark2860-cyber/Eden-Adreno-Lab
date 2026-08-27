# Handoff Prompt — Eden Adreno X1 Uniform cache A/B

Use this prompt when continuing the work in a new tab.

---

Eden Windows ARM64 / Snapdragon X / Adreno X1-85 구동분석 작업을 이어간다.

GitHub 저장소 `npark2860-cyber/Eden-Adreno-Lab`에서 현재 실험 브랜치 `exp/x1-uniform-payload-fingerprint`의 실제 HEAD를 먼저 확인하고, 다음 문서를 기준 상태로 읽어라:

1. `CURRENT_HANDOFF.md`
2. `DEBUG_HISTORY.md`
3. `LAB_BOOTSTRAP.md`
4. `NEXT_ACTION_UNIFORM_CACHE_AB.md`

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
- 따라서 다음 실험은 custom dedupe/reuse가 아니라 기존 classic cached path를 사용하는 policy A/B여야 한다.

`NEXT_ACTION_UNIFORM_CACHE_AB.md`의 지시대로 새 브랜치 `exp/x1-uniform-cache-ab`를 준비하고, Qualcomm/X1 전용 debug checkbox를 default OFF로 추가하라.

A/B OFF는 exact existing behavior를 보존해야 한다.

A/B ON은 오직 adaptive `fastSkip`만 fast mapped-stream 선택에서 제외하고 classic cached `SynchronizeBuffer()` path로 떨어뜨려야 한다. `needs_alignment_stream`은 그대로 fast path를 강제해야 한다.

scheduler, alias copy, barrier, render-pass request, dirty-state semantics, staging/descriptor lifetime은 건드리지 마라. persistent Uniform binding을 켜지 말고 previous staging allocation 재사용도 구현하지 마라.

정적 검증과 workflow 준비까지만 진행해라.

ARM64 GitHub Actions는 사용자의 fresh explicit authorization 없이는 절대 시작하거나 재실행하지 마라. 한 번의 승인 = 정확히 한 번의 build attempt다.

현재 최신 성공 payload diagnostic build는:

- workflow `Build dc95 X1 Uniform Payload Fingerprint`
- run `33040377420`
- job `98412364840`
- attempt 1
- build HEAD `9f1a916c7eaa72f3921cfa49233756dbbba5c3d9`
- artifact `Eden-dc95-X1-uniform-payload-fingerprint`
- artifact id `9634160587`
- SHA-256 `de68710492c8c221a8936cef97bb6d876dd44f409cd2d75074cee18bcab6106f`

작업 중 새로 확정되는 사실과 실험 결과는 `DEBUG_HISTORY.md`에 누적하고, 다음 탭이 바로 이어갈 수 있도록 `CURRENT_HANDOFF.md`를 항상 최신으로 유지해라.
