# DevSecOps-Project-Repo

OpsGuard 통합 레포지토리 — Runtime, Regulation, Finance Agent 및 MCP Orchestrator.

## AWS SAM 배포

GuardDuty → MCP → Agent 파이프라인을 SAM으로 배포하는 방법은 **[SAM-DEPLOY.md](./SAM-DEPLOY.md)** 를 참고하세요.

```bash
cd DevSecOps-Project-Repo
sam validate --lint
sam build
sam deploy --guided   # 최초
sam build && sam deploy   # 이후
```

## 구성 요소

| 디렉터리 | 역할 |
|----------|------|
| `DevSecOps-MCP/` | MCP Orchestrator, Slack Response |
| `DevSecOps-Runtime_Agent/` | Level 1~3 자동/승인 대응 |
| `DevSecOps-Finance_Agent/` | 비용 분석·시뮬레이션 |
| `DevSecOps-Regulation_Agent/` | ChromaDB RAG 규제 분석 (컨테이너) |
