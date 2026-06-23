# OpsGuard — AWS SAM 배포 가이드

GuardDuty Finding → MCP Orchestrator → Runtime / Finance / Regulation Agent 파이프라인을 AWS SAM으로 배포합니다.

## 아키텍처

```
GuardDuty Finding
       │
       ▼ (EventBridge: guardduty-to-mcp)
    ┌──────┐
    │ MCP  │──invoke──▶ Runtime_Agent
    └──┬───┘──invoke──▶ Finance_Agent
       │    invoke──▶ Regulation_Agent_20260616 (Container)
       │
       ▼ DynamoDB PutItem (Regulation_JSON)

Slack App ──POST──▶ HTTP API /slack/events ──▶ MCP-Slack-Response
                                                    │
                                    invoke Runtime / Finance
```

## 사전 요구사항

| 항목 | 설명 |
|------|------|
| AWS CLI | `aws configure` 완료, `ap-northeast-2` 리전 |
| AWS SAM CLI | [설치 가이드](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html) |
| Docker | Regulation Agent 컨테이너 이미지 빌드용 (`sam build` 시 필요) |
| Secrets Manager | `opsguard/openai`, `opsguard/slack` 시크릿 존재 |
| 기존 리소스 | DynamoDB `AgentB_Response_History`, `Regulation_JSON`, S3 `mcp-security-logs-bucket`, WAF IPSet, VPC Flow Log Role |

### Python 런타임 참고

| 함수 | SAM 런타임 | 비고 |
|------|-----------|------|
| MCP | python3.11 | |
| MCP-Slack-Response | python3.11 | 콘솔에 Python 3.14로 보일 수 있으나 Lambda 미지원 → **3.11로 통일** |
| Runtime_Agent | python3.11 | |
| Finance_Agent | python3.11 | |
| Regulation_Agent_20260616 | Container (Python 3.11 base) | `Dockerfile` 기준 |

### Regulation Agent — ChromaDB 데이터

`DevSecOps-Regulation_Agent/chroma_db/`는 `.gitignore` 대상입니다. **이미지 빌드 전** 반드시 로컬에 배치하세요.

```bash
# 예: S3 또는 기존 ECR 이미지에서 chroma_db 복원
aws s3 sync s3://YOUR-BUCKET/chroma_db/ DevSecOps-Regulation_Agent/chroma_db/
```

Dockerfile은 `chroma_db`를 이미지에 포함하고, Lambda 런타임에서 `/tmp/chroma_db`로 복사해 사용합니다 (`service.py`).

## 폴더 ↔ Lambda 매핑

| Lambda 함수 | CodeUri / DockerContext | Handler |
|-------------|-------------------------|---------|
| MCP | `DevSecOps-MCP/src/MCP/` | `lambda_function.lambda_handler` |
| MCP-Slack-Response | `DevSecOps-MCP/src/MCP-Slack-Response/` | `lambda_function.lambda_handler` |
| Runtime_Agent | `DevSecOps-Runtime_Agent/` | `lambda_function.lambda_handler` |
| Finance_Agent | `DevSecOps-Finance_Agent/` | `handler.lambda_handler` |
| Regulation_Agent_20260616 | `DevSecOps-Regulation_Agent/` (Image) | `lambda_function.lambda_handler` |

## Secrets Manager (하드코딩 금지)

`template.yaml`에서 CloudFormation 동적 참조로 주입됩니다. 배포 주체(IAM)에 `secretsmanager:GetSecretValue` 권한이 필요합니다.

| 환경 변수 | 시크릿 참조 |
|-----------|------------|
| `OPENAI_API_KEY` | `{{resolve:secretsmanager:opsguard/openai:SecretString:OPENAI_API_KEY}}` |
| `SLACK_BOT_TOKEN` | `{{resolve:secretsmanager:opsguard/slack:SecretString:SLACK_BOT_TOKEN}}` |
| `SLACK_WEBHOOK_URL` | `{{resolve:secretsmanager:opsguard/slack:SecretString:SLACK_WEBHOOK_URL}}` |

## 배포 명령어

`DevSecOps-Project-Repo` 루트에서 실행합니다.

### 1. 템플릿 검증

```bash
cd DevSecOps-Project-Repo
sam validate --lint
```

### 2. 빌드

```bash
sam build
```

Regulation Agent는 Docker 이미지를 빌드합니다. 최초 배포 시 ECR 리포지토리가 자동 생성됩니다 (`resolve_image_repos = true`).

### 3. 최초 배포 (대화형)

```bash
sam deploy --guided
```

안내에 따라 스택 이름(`opsguard`), 리전(`ap-northeast-2`), **SlackChannel** 등을 입력합니다.

### 4. 이후 배포

`samconfig.toml`의 `parameter_overrides`에서 `SlackChannel`을 실제 채널 ID로 수정한 뒤:

```bash
sam build && sam deploy
```

### 5. 배포 결과 확인

```bash
aws cloudformation describe-stacks \
  --stack-name opsguard \
  --region ap-northeast-2 \
  --query "Stacks[0].Outputs"
```

주요 Output:

- **SlackEventsApiUrl** — Slack App Request URL (`https://{api-id}.execute-api.ap-northeast-2.amazonaws.com/slack/events`)
- **MCPFunctionArn**
- **RuntimeAgentFunctionArn**
- **FinanceAgentFunctionArn**
- **RegulationAgentFunctionArn**

## Slack App 설정

1. [Slack API](https://api.slack.com/apps)에서 앱 선택
2. **Event Subscriptions** → Request URL에 `SlackEventsApiUrl` 값 입력
3. **Interactivity** 활성화 (동일 URL 또는 별도 설정에 맞게 조정)

## GuardDuty severity 필터 (선택)

기본값은 **모든 GuardDuty Finding**을 처리합니다. `severity >= 7` (HIGH/CRITICAL)만 처리하려면 `template.yaml`의 `McpFunction` → `Events` → `GuardDutyFinding` → `Pattern`에서 주석 처리된 `detail.severity` 블록의 주석을 해제하세요.

```yaml
detail:
  severity:
    - numeric:
        - '>='
        - 7
```

수정 후 `sam build && sam deploy`로 반영합니다.

## Parameter 커스터마이징

`sam deploy` 시 `--parameter-overrides`로 기존 리소스를 지정할 수 있습니다.

```bash
sam deploy \
  --parameter-overrides \
    SlackChannel=C0XXXXXXX \
    DynamoDbTableArn=arn:aws:dynamodb:ap-northeast-2:836347236184:table/AgentB_Response_History \
    S3LogBucketName=mcp-security-logs-bucket \
    WafIpSetId=657906ea-7bc5-4c48-b500-6b2686fdb9d2 \
    RegulationImageTag=deploy-20260623-120000
```

## IAM 정책 요약

- **MCP**: Runtime / Finance / Regulation / MCP-Slack-Response `lambda:InvokeFunction`만 허용 (와일드카드 `function:*` 미사용)
- **MCP-Slack-Response**: Runtime / Finance invoke, `Regulation_JSON` `GetItem`
- **Runtime_Agent**: DynamoDB 이력, IAM/EC2/S3/WAF/CloudTrail 최소 권한 (`s3:PutPublicAccessBlock` 사용)
- **Finance / Regulation**: CloudWatch Logs (시크릿은 배포 시 env 주입)

## 트러블슈팅

| 증상 | 확인 사항 |
|------|----------|
| `sam validate` 실패 | SAM CLI 버전 ≥ 1.100, `template.yaml` YAML 문법 |
| Regulation 이미지 빌드 실패 | Docker 실행 여부, `chroma_db/` 존재 여부 |
| Slack 403 / URL 검증 실패 | `SlackEventsApiUrl`이 API Gateway `$default` 스테이지와 일치하는지 |
| MCP가 Agent 호출 실패 | CloudWatch Logs에서 IAM `AccessDenied`, ARN 환경변수 확인 |
| Secrets resolve 실패 | 배포 IAM에 `secretsmanager:GetSecretValue` on `opsguard/*` |

## 로컬 테스트 (선택)

```bash
# MCP 이벤트 샘플 invoke (배포 후)
aws lambda invoke \
  --function-name MCP \
  --region ap-northeast-2 \
  --payload file://DevSecOps-Runtime_Agent/test_event.json \
  response.json
```

## 관련 파일

- `template.yaml` — SAM/CloudFormation IaC
- `samconfig.toml` — 배포 기본값
- `.samignore` — 빌드 제외 경로
