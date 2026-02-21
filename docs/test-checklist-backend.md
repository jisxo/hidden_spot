# Hidden Spot Backend Manual Test Checklist

자동 테스트 도구 없이 백엔드 API/파이프라인을 점검하기 위한 수동 테스트 항목입니다.

## 1. 서비스 기동
- [ ] `api`, `worker`, `redis`, `postgres`, `minio`가 정상 기동한다.
- [ ] API 헬스체크(`GET /health`)가 `200`을 반환한다.

## 2. 작업 생성/조회
- [ ] `POST /jobs` 호출 시 `202`와 `job_id/run_id/store_id`를 반환한다.
- [ ] `GET /jobs/{job_id}` 조회 시 `queued` 또는 `started` 상태를 확인할 수 있다.
- [ ] 작업 완료 후 `GET /jobs/{job_id}`에서 최종 `completed`를 확인한다.

## 3. 큐/워커 처리
- [ ] 요청 1건당 워커 잡이 1회 enqueue 된다.
- [ ] 워커 로그에서 단계별 처리(수집/정제/분석/저장)가 확인된다.
- [ ] 실패 시 에러 사유가 로그에 남는다.

## 4. 산출물 저장
- [ ] MinIO Bronze 경로에 수집 원본 오브젝트가 생성된다.
- [ ] MinIO Silver 경로에 정제 결과 오브젝트가 생성된다.
- [ ] MinIO Gold 경로에 분석 결과 오브젝트가 생성된다.

## 5. DB 반영
- [ ] Postgres `store_snapshots` 상태가 `queued -> completed`로 갱신된다.
- [ ] Postgres `analysis` 테이블에 upsert 된다.
- [ ] 동일 `store_id` 재요청 시 중복/충돌 없이 상태와 결과가 갱신된다.

## 6. 검색/조회 API
- [ ] `GET /search/smart?q=<keyword>` 호출 시 `query/expanded_terms/items` 구조를 반환한다.
- [ ] 결과 개수 제한(`limit`)이 정상 동작한다.

## 7. 실패/예외 시나리오
- [ ] 잘못된 요청 본문(빈 URL 등)에서 `400` 에러를 반환한다.
- [ ] 존재하지 않는 잡 조회 시 `404`를 반환한다.
- [ ] 외부 의존성 장애(예: Redis/Postgres 비가용) 시 API가 적절한 실패 응답/로그를 남긴다.

## 8. 관측/운영
- [ ] API/워커 로그에서 `run_id` 기반 추적이 가능하다.
- [ ] 동일 시점 다중 요청에서도 잡 식별(`run_id`)이 충돌하지 않는다.
- [ ] 장시간 실행 시 메모리 급증/비정상 종료가 없다.

## 기록 템플릿
- 테스트 일시:
- 테스트 환경(로컬/도커, OS):
- 커밋/배포 버전:
- 실패 항목:
- 재현 절차:
- 관련 로그(run_id, 서비스 로그 위치):
