"""평가용 프롬프트: LLM-as-Judge 판정, answer_relevancy 용 질문 역생성."""

JUDGE_PROMPT = """너는 야구학습센터 예약 Agent 의 평가자다. 아래 자료를 보고 JSON 만 출력한다.

[사용자 질문]
{question}

[Agent 답변]
{answer}

[근거 contexts (번호 순서대로)]
{contexts}

[기대 항목 expected_traits]
{traits}

다음을 판정해 JSON 으로 답한다.
1. traits: 기대 항목마다 답변이 충족하는지. [{{"trait": 항목, "pass": true/false, "reason": 짧은 이유}}]
2. claims: 답변 속 사실 주장(인사말·질문 제외)을 나열하고, 각 주장이 contexts 로 뒷받침되는지. [{{"claim": 주장, "supported": true/false}}]
3. context_relevance: contexts 번호 순서대로, 각 context 가 기대 항목을 만족하는 답을 만드는 데 쓸모 있는지. [true/false, ...]
4. reference_support: 기대 항목마다 그 내용이 contexts 로 뒷받침되는지(답변 형식·태도에 관한 항목은 true). [true/false, ...]

출력 형식: {{"traits": [...], "claims": [...], "context_relevance": [...], "reference_support": [...]}}"""

QUESTION_GEN_PROMPT = """다음 답변을 보고, 이 답변이 대답하고 있을 법한 사용자 질문 3개를 한국어로 만들어라.
JSON 배열로만 출력한다. 예: ["질문1", "질문2", "질문3"]

[답변]
{answer}"""
