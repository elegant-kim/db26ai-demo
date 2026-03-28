const { createApp, ref, reactive, nextTick, onMounted, computed } = Vue;

const app = createApp({
    delimiters: ['[[', ']]'],

    setup() {
        // === Common State ===
        const activeTab = ref('nl2sql');
        const dbConnected = ref(false);
        const schema = ref('');
        const profiles = ref([]);
        const selectedProfile = ref('');

        const toast = reactive({
            show: false,
            message: '',
            type: 'success',
        });

        // === NL2SQL State ===
        const userInput = ref('');
        const sqlInput = ref('');
        const isLoading = ref(false);
        const isSqlLoading = ref(false);
        const selectedAction = ref('showsql');
        const messages = ref([]);
        const chatMessages = ref(null);
        const chartInstances = {};

        // === Profile Info State ===
        const profileInfo = ref(null);
        const schemaInfo = ref(null);
        const schemaLoading = ref(false);
        const schemaExpanded = ref({});
        const annotationApplying = ref(false);
        const annotationRemoving = ref(false);

        // SH 스키마 Annotation 세트
        const annotationSets = {
            SH: {
                CUSTOMERS: {
                    _table: '고객 마스터 테이블 - 인구통계 및 신용정보 포함',
                    CUST_ID: '고객 고유 식별자 (PK)',
                    CUST_FIRST_NAME: '고객 이름 (First Name)',
                    CUST_LAST_NAME: '고객 성 (Last Name)',
                    CUST_GENDER: '성별: M=Male, F=Female',
                    CUST_YEAR_OF_BIRTH: '출생연도 (4자리)',
                    CUST_MARITAL_STATUS: '결혼상태: married, single 등',
                    CUST_STREET_ADDRESS: '거주지 주소',
                    CUST_POSTAL_CODE: '우편번호',
                    CUST_CITY: '거주 도시',
                    CUST_STATE_PROVINCE: '거주 주/도',
                    CUST_MAIN_PHONE_NUMBER: '주요 전화번호',
                    CUST_INCOME_LEVEL: '소득구간: A: Under 30,000 ~ L: 300,000 and above',
                    CUST_CREDIT_LIMIT: '신용한도 (USD)',
                    CUST_EMAIL: '이메일 주소',
                    CUST_VALID: '고객 유효 상태: A=Active, I=Inactive',
                },
                SALES: {
                    _table: '판매 트랜잭션 팩트 테이블',
                    PROD_ID: '제품 ID (FK: PRODUCTS.PROD_ID)',
                    CUST_ID: '고객 ID (FK: CUSTOMERS.CUST_ID)',
                    TIME_ID: '판매 일자 (FK: TIMES.TIME_ID)',
                    CHANNEL_ID: '판매 채널 ID (FK: CHANNELS.CHANNEL_ID)',
                    PROMO_ID: '프로모션 ID (FK: PROMOTIONS.PROMO_ID)',
                    QUANTITY_SOLD: '판매 수량',
                    AMOUNT_SOLD: '판매 금액 (USD)',
                },
                PRODUCTS: {
                    _table: '제품 마스터 테이블',
                    PROD_ID: '제품 고유 식별자 (PK)',
                    PROD_NAME: '제품명',
                    PROD_DESC: '제품 설명',
                    PROD_SUBCATEGORY: '제품 소분류',
                    PROD_CATEGORY: '제품 대분류',
                    PROD_STATUS: '제품 상태: Status 값으로 활성여부 판단',
                    PROD_LIST_PRICE: '정가 (USD)',
                    PROD_MIN_PRICE: '최저가 (USD)',
                },
                CHANNELS: {
                    _table: '판매 채널 (Direct Sales, Internet, Catalog, Partners)',
                    CHANNEL_ID: '채널 고유 식별자 (PK)',
                    CHANNEL_DESC: '채널명: Direct Sales, Internet, Catalog, Partners',
                    CHANNEL_CLASS: '채널 분류: Direct, Indirect, Others',
                },
                TIMES: {
                    _table: '시간 차원 테이블 (1998~2001년)',
                    TIME_ID: '날짜 (PK)',
                    DAY_NAME: '요일명 (Monday~Sunday)',
                    CALENDAR_MONTH_DESC: '월 (예: 2000-01)',
                    CALENDAR_QUARTER_DESC: '분기 (예: 2000-Q1)',
                    CALENDAR_YEAR: '연도 (예: 2000)',
                    FISCAL_YEAR: '회계연도',
                },
                PROMOTIONS: {
                    _table: '프로모션 정보',
                    PROMO_ID: '프로모션 ID (PK)',
                    PROMO_NAME: '프로모션명',
                    PROMO_SUBCATEGORY: '프로모션 소분류',
                    PROMO_CATEGORY: '프로모션 대분류',
                },
                COUNTRIES: {
                    _table: '국가 정보 (고객 국가 참조)',
                    COUNTRY_ID: '국가 ID (PK)',
                    COUNTRY_NAME: '국가명',
                    COUNTRY_REGION: '대륙/지역 (Americas, Europe, Asia 등)',
                    COUNTRY_SUBREGION: '세부지역',
                },
                COSTS: {
                    _table: '제품 원가 테이블',
                    PROD_ID: '제품 ID (FK)',
                    TIME_ID: '날짜 (FK)',
                    UNIT_COST: '단위 원가 (USD)',
                    UNIT_PRICE: '단위 판매가 (USD)',
                },
            },
        };

        // === Vector Search State ===
        const vectorSubMenu = ref('load');  // 'load', 'table', 'upload', 'search', 'query'
        const vectorInput = ref('');
        const vectorLoading = ref(false);
        const vectorSearchMode = ref('vector');
        const vectorMessages = ref([]);
        const vectorChatMessages = ref(null);
        const uploadedDocs = ref([]);
        const isUploading = ref(false);
        const dragOver = ref(false);

        // Step 1: Table Management State
        const tableActionLoading = ref(false);
        const tableActionResult = ref(null);

        // Step 2: Table Inspection State
        const tableInspectTarget = ref('DOC_CHUNKS');
        const tableDefResult = ref(null);
        const tableDataResult = ref(null);
        const tableIdxResult = ref(null);
        const tableDefLoading = ref(false);
        const tableDataLoading = ref(false);
        const tableIdxLoading = ref(false);

        // Step 4: Query Inspection State
        const recentSqlResult = ref(null);
        const explainPlanResult = ref(null);
        const recentSqlLoading = ref(false);
        const explainPlanLoading = ref(false);

        // === AWR Analyzer State ===
        const extraSubMenu = ref('awr-upload');
        const awrProfileName = ref('');
        const awrLoading = ref(false);
        const awrError = ref('');
        const awrAnalysis = ref(null);
        const awrFilename = ref('');
        const awrParseInfo = ref({});
        const awrElapsedMs = ref(0);
        const awrSessionId = ref('');
        const awrDragOver = ref(false);
        const awrFollowupInput = ref('');
        const awrFollowupLoading = ref(false);
        const awrFollowupMessages = ref([]);
        const awrFollowupMessagesRef = ref(null);

        // === Constants ===
        const actionModesLeft = [
            { value: 'showsql', label: 'SQL 보기' },
            { value: 'narrate', label: '설명' },
            { value: 'showprompt', label: '프롬프트' },
            { value: 'chat', label: '대화' },
        ];
        const actionModesRight = [
            { value: 'runsql', label: '실행' },
            { value: 'explainsql', label: 'SQL 해설' },
            { value: 'summarize', label: '요약' },
        ];

        const exampleQuestionsMap = {
            SH: [
                '매출 상위 5개 제품을 알려주세요',
                '월별 매출 추이를 알려주세요',
                '국가별 고객 수를 알려주세요',
                '연도별 총 매출액을 알려주세요',
                '채널별 주문 건수를 알려주세요',
                '2000년 인터넷 채널에서 가장 많이 판매된 제품 카테고리 상위 3개와 매출액을 알려줘',
                '미국 고객 중 연간 구매금액이 가장 높은 상위 10명의 이름과 총 구매금액은?',
                '프로모션 유형별 평균 할인율과 그에 따른 매출 변화를 분석해줘',
                '분기별 매출 성장률을 전년 동기 대비로 보여줘',
                '고객 연령대별 선호 제품 카테고리와 평균 구매단가를 알려줘',
                // Annotation 데모용 질문
                '유효한 고객 수를 알려줘',
                '유효하지 않은 고객 중 신용한도가 가장 높은 5명은?',
                '소득구간별 고객 수와 평균 신용한도를 보여줘',
                '인터넷 채널과 직접판매 채널의 매출 비교',
            ],
            SSB: [
                '총 매출액이 가장 높은 공급업체 5곳을 알려줘',
                '연도별 총 주문금액 추이를 보여줘',
                '지역별 고객 수와 평균 주문금액을 알려줘',
                '제품 브랜드별 판매수량 순위를 알려줘',
                '월별 주문건수와 평균 할인율을 보여줘',
                '1997년에 아시아 지역 고객이 주문한 제품 중 매출 상위 5개 브랜드는?',
                '공급업체 국가별 평균 공급비용과 총 매출을 비교해줘',
                '할인율 20% 이상 적용된 주문의 연도별 매출 비중을 분석해줘',
                '제품 카테고리별 수익성(매출-공급비용)이 가장 높은 상위 5개 제품은?',
                '분기별 주문량 추이와 전분기 대비 증감률을 보여줘',
            ],
            DEFAULT: [
                '테이블 목록을 보여줘',
                '전체 레코드 수를 알려줘',
                '최근 데이터 10건을 보여줘',
            ],
        };
        const exampleQuestions = ref(exampleQuestionsMap.SH);

        const vectorExampleQuestions = ref([
            '연차 사용 규정을 알려주세요',
            '퇴직금 산정 기준을 알려주세요',
            '출장비 정산 절차를 알려주세요',
        ]);

        const loadingMessageMap = {
            showsql: 'AI가 SQL을 생성하고 있습니다',
            runsql: 'AI가 SQL을 생성하고 실행하고 있습니다',
            narrate: 'AI가 자연어 설명을 생성하고 있습니다',
            explainsql: 'AI가 SQL 해설을 작성하고 있습니다',
            showprompt: 'AI 프롬프트를 조회하고 있습니다',
            summarize: 'AI가 요약을 생성하고 있습니다',
            chat: 'AI가 응답을 생성하고 있습니다',
        };

        const vectorLoadingMessages = [
            '질문 임베딩 중...',
            '벡터 유사도 검색 중...',
            '참조 문서 수집 중...',
            'RAG 답변 생성 중...',
        ];

        // === Action button rules ===
        const actionButtonRules = {
            runsql: [
                { action: 'showsql', label: 'SQL 보기' },
                { action: 'chart', label: '차트' },
                { action: 'narrate', label: '설명' },
                { action: 'explainsql', label: 'SQL 해설' },
                { action: 'explainplan', label: '실행계획' },
                { action: 'showprompt', label: '프롬프트 보기' },
                { action: 'summarize', label: '요약' },
            ],
            showsql: [
                { action: 'runsql', label: '실행' },
                { action: 'narrate', label: '설명' },
                { action: 'explainsql', label: 'SQL 해설' },
                { action: 'explainplan', label: '실행계획' },
                { action: 'showprompt', label: '프롬프트 보기' },
            ],
            narrate: [
                { action: 'showsql', label: 'SQL 보기' },
                { action: 'runsql', label: '실행' },
                { action: 'showprompt', label: '프롬프트 보기' },
            ],
            explainsql: [
                { action: 'showsql', label: 'SQL 보기' },
                { action: 'runsql', label: '실행' },
                { action: 'showprompt', label: '프롬프트 보기' },
            ],
            showprompt: [
                { action: 'showsql', label: 'SQL 보기' },
                { action: 'runsql', label: '실행' },
            ],
            summarize: [
                { action: 'showsql', label: 'SQL 보기' },
                { action: 'runsql', label: '실행' },
                { action: 'chart', label: '차트' },
                { action: 'showprompt', label: '프롬프트 보기' },
            ],
            chat: [],
        };

        // === Common Methods ===

        function showToast(message, type = 'success') {
            toast.show = true;
            toast.message = message;
            toast.type = type;
            setTimeout(() => { toast.show = false; }, 3000);
        }

        function formatTime() {
            const now = new Date();
            return now.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
        }

        function setPrompt(text) {
            userInput.value = text;
        }

        function scrollToBottom() {
            nextTick(() => {
                if (chatMessages.value) {
                    chatMessages.value.scrollTop = chatMessages.value.scrollHeight;
                }
            });
        }

        function scrollVectorToBottom() {
            nextTick(() => {
                if (vectorChatMessages.value) {
                    vectorChatMessages.value.scrollTop = vectorChatMessages.value.scrollHeight;
                }
            });
        }

        // === Oracle SQL Highlighting ===
        function highlightOracleSQL(sql) {
            if (!sql) return '';
            let s = sql.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

            // Oracle-specific functions (Oracle Red)
            s = s.replace(/\b(VECTOR_DISTANCE|VECTOR_EMBEDDING|DBMS_VECTOR_CHAIN\.UTL_TO_CHUNKS|DBMS_CLOUD_AI\.GENERATE|DBMS_LOB\.SUBSTR|DBMS_XPLAN\.DISPLAY|VECTOR_SERIALIZE|VECTOR_INDEX_TRANSFORM)\b/g,
                '<span style="color: #C74634; font-weight: 600;">$1</span>');

            // String literals (green)
            s = s.replace(/'([^']*)'/g, '<span style="color: #16a34a;">\'$1\'</span>');

            // SQL keywords (purple)
            const keywords = ['SELECT', 'FROM', 'WHERE', 'ORDER BY', 'FETCH FIRST', 'ROWS ONLY',
                'INSERT INTO', 'VALUES', 'UPDATE', 'SET', 'DELETE', 'CREATE', 'TABLE',
                'INDEX', 'ON', 'AS', 'AND', 'OR', 'NOT', 'NULL', 'IS', 'IN', 'LIKE',
                'CONTAINS', 'INTO', 'BEGIN', 'END', 'DECLARE', 'USING', 'BY',
                'DESC', 'ASC', 'JOIN', 'INNER', 'LEFT', 'RIGHT', 'GROUP', 'HAVING',
                'DISTINCT', 'COUNT', 'SUM', 'AVG', 'MAX', 'MIN', 'LOWER', 'UPPER',
                'SCORE', 'COSINE', 'ORGANIZATION', 'NEIGHBOR', 'PARTITIONS', 'DISTANCE',
                'VECTOR', 'CLOB', 'NUMBER', 'VARCHAR2', 'TIMESTAMP', 'IDENTITY', 'PRIMARY KEY',
                'INMEMORY', 'GRAPH', 'WITH', 'TARGET', 'ACCURACY', 'CASCADE', 'CONSTRAINTS',
                'PURGE', 'DROP', 'EXPLAIN', 'PLAN', 'FOR', 'SUBSTR', 'CASE', 'WHEN', 'THEN', 'ELSE',
                'FETCH APPROX FIRST', 'USER_TAB_COLUMNS', 'USER_INDEXES', 'USER_IND_COLUMNS',
                'COLUMN_ID', 'COLUMN_NAME', 'DATA_TYPE', 'DATA_LENGTH', 'NULLABLE'];
            for (const kw of keywords) {
                const regex = new RegExp(`\\b(${kw})\\b`, 'gi');
                s = s.replace(regex, (match) => {
                    return `<span style="color: #7c3aed;">${match}</span>`;
                });
            }

            return s;
        }

        function highlightSQLWithLines(sql) {
            if (!sql) return '';
            const lines = sql.split('\n');
            return lines.map((line, i) => {
                const num = `<span class="sql-line-num">${i + 1}</span>`;
                const highlighted = highlightOracleSQL(line);
                return `<div class="sql-line">${num}${highlighted}</div>`;
            }).join('');
        }

        // === NL2SQL Methods ===

        function getActionButtons(msg) {
            const rules = actionButtonRules[msg.action] || [];
            return rules.filter(btn => {
                if (btn.action === 'chart') {
                    return msg.tableData && msg.tableData.length > 0;
                }
                return true;
            });
        }

        async function sendQuestion() {
            const prompt = userInput.value.trim();
            if (!prompt || isLoading.value) return;

            const action = selectedAction.value;
            const profileName = selectedProfile.value;

            // 이전 질문 찾기 (같은 프로필의 마지막 user 메시지)
            let prevPrompt = null;
            for (let i = messages.value.length - 1; i >= 0; i--) {
                const m = messages.value[i];
                if (m.role === 'user' && !m.isSql) {
                    prevPrompt = m.content;
                    break;
                }
            }

            messages.value.push({
                role: 'user',
                content: prompt,
                prevPrompt: prevPrompt,
                timestamp: formatTime(),
            });

            userInput.value = '';

            const baseLoadingText = loadingMessageMap[action] || 'AI가 처리하고 있습니다';
            const assistantMsg = reactive({
                role: 'assistant',
                action: action,
                prompt: prompt,
                profileName: profileName,
                loading: true,
                loadingText: baseLoadingText + '... (0초)',
                sql: null,
                tableData: null,
                textResult: null,
                error: null,
                elapsed_ms: null,
                showChart: false,
                chartType: 'bar',
                sqlExpanded: true,
                actionLoading: false,
                actionLoadingText: '',
                cachedActions: {},
                timestamp: formatTime(),
            });
            messages.value.push(assistantMsg);
            scrollToBottom();

            isLoading.value = true;
            let elapsedSec = 0;
            const loadingInterval = setInterval(() => {
                elapsedSec++;
                assistantMsg.loadingText = baseLoadingText + `... (${elapsedSec}초)`;
            }, 1500);

            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 120000);
                const response = await fetch('/api/ask', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt, action, profile_name: profileName }),
                    signal: controller.signal,
                });
                clearTimeout(timeoutId);

                const data = await response.json();
                clearInterval(loadingInterval);

                if (data.success) {
                    assistantMsg.elapsed_ms = data.elapsed_ms;
                    processResult(assistantMsg, action, data.result);
                    assistantMsg.cachedActions[action] = data.result;
                } else {
                    assistantMsg.error = data.error || '알 수 없는 오류가 발생했습니다.';
                }
            } catch (err) {
                clearInterval(loadingInterval);
                if (err.name === 'AbortError') {
                    assistantMsg.error = '요청 시간이 초과되었습니다 (120초). 질문을 단순화하거나 다시 시도해 주세요.';
                } else {
                    assistantMsg.error = '서버 연결에 실패했습니다: ' + err.message;
                }
            } finally {
                assistantMsg.loading = false;
                isLoading.value = false;
                scrollToBottom();
            }
        }

        async function executeSql() {
            const sql = sqlInput.value.trim();
            if (!sql || isSqlLoading.value) return;

            messages.value.push({
                role: 'user',
                content: sql,
                timestamp: formatTime(),
                isSql: true,
            });
            sqlInput.value = '';

            const assistantMsg = reactive({
                role: 'assistant',
                action: 'rawsql',
                loading: true,
                loadingText: 'SQL 실행 중...',
                sqlResult: null,
                error: null,
                elapsed_ms: null,
                timestamp: formatTime(),
            });
            messages.value.push(assistantMsg);
            scrollToBottom();

            isSqlLoading.value = true;
            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 120000);
                const response = await fetch('/api/execute-sql', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ sql }),
                    signal: controller.signal,
                });
                clearTimeout(timeoutId);
                const data = await response.json();
                if (data.success) {
                    assistantMsg.elapsed_ms = data.elapsed_ms;
                    assistantMsg.sqlResult = {
                        sql_executed: data.sql_executed,
                        columns: data.columns,
                        data: data.data,
                        row_count: data.row_count,
                    };
                } else {
                    assistantMsg.error = data.error || 'SQL 실행에 실패했습니다.';
                    if (data.sql_executed) {
                        assistantMsg.sqlResult = { sql_executed: data.sql_executed };
                    }
                }
            } catch (err) {
                if (err.name === 'AbortError') {
                    assistantMsg.error = '요청 시간이 초과되었습니다 (120초). 질문을 단순화하거나 다시 시도해 주세요.';
                } else {
                    assistantMsg.error = '서버 연결에 실패했습니다: ' + err.message;
                }
            } finally {
                assistantMsg.loading = false;
                isSqlLoading.value = false;
                scrollToBottom();
            }
        }

        function processResult(msg, action, result) {
            if (action === 'runsql') {
                if (Array.isArray(result) && result.length > 0 && typeof result[0] === 'object') {
                    msg.tableData = result;
                } else if (typeof result === 'string') {
                    try {
                        const parsed = JSON.parse(result);
                        if (Array.isArray(parsed)) {
                            msg.tableData = parsed;
                        } else {
                            msg.textResult = typeof result === 'string' ? result : JSON.stringify(result, null, 2);
                        }
                    } catch {
                        msg.textResult = result;
                    }
                } else {
                    msg.textResult = typeof result === 'string' ? result : JSON.stringify(result, null, 2);
                }
            } else if (action === 'showsql') {
                msg.sql = typeof result === 'string' ? result : JSON.stringify(result, null, 2);
                msg.sqlExpanded = true;
            } else {
                msg.textResult = typeof result === 'string' ? result : JSON.stringify(result, null, 2);
            }
        }

        async function executeAction(msgIdx, action) {
            const msg = messages.value[msgIdx];
            if (!msg || msg.actionLoading) return;

            if (action === 'chart') {
                msg.showChart = !msg.showChart;
                if (msg.showChart) {
                    nextTick(() => renderChart(msgIdx));
                }
                return;
            }

            // 실행계획: showsql 캐시에서 SQL 추출 후 /api/explain-plan 호출
            if (action === 'explainplan') {
                // SQL 텍스트 확보 (showsql 캐시 또는 현재 msg.sql)
                let sqlText = msg.sql;
                if (!sqlText && msg.cachedActions && msg.cachedActions['showsql']) {
                    sqlText = msg.cachedActions['showsql'];
                }
                if (!sqlText) {
                    // showsql을 먼저 호출하여 SQL 획득
                    showToast('SQL을 먼저 확인해주세요. (SQL 보기 클릭)', 'error');
                    return;
                }
                if (msg.cachedActions && msg.cachedActions['explainplan']) {
                    msg.explainPlan = msg.cachedActions['explainplan'];
                    msg.action = 'explainplan';
                    scrollToBottom();
                    return;
                }
                msg.actionLoading = true;
                msg.actionLoadingText = '실행계획을 조회하고 있습니다... (0초)';
                let planElapsed = 0;
                const planTimer = setInterval(() => {
                    planElapsed++;
                    msg.actionLoadingText = `실행계획을 조회하고 있습니다... (${planElapsed}초)`;
                }, 1000);
                try {
                    const response = await fetch('/api/explain-plan', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ sql: sqlText }),
                    });
                    const data = await response.json();
                    if (data.success) {
                        msg.explainPlan = data.plan;
                        msg.cachedActions['explainplan'] = data.plan;
                        msg.action = 'explainplan';
                    } else {
                        showToast(data.error || '실행계획 조회 실패', 'error');
                    }
                } catch (err) {
                    showToast('실행계획 조회 실패: ' + err.message, 'error');
                } finally {
                    clearInterval(planTimer);
                    msg.actionLoading = false;
                    msg.actionLoadingText = '';
                    scrollToBottom();
                }
                return;
            }

            if (msg.cachedActions && msg.cachedActions[action]) {
                processResult(msg, action, msg.cachedActions[action]);
                msg.action = action;
                scrollToBottom();
                return;
            }

            const actionLabel = loadingMessageMap[action] || 'AI가 처리하고 있습니다';
            msg.actionLoading = true;
            msg.actionLoadingText = actionLabel + '... (0초)';
            let actionElapsed = 0;
            const actionTimer = setInterval(() => {
                actionElapsed++;
                msg.actionLoadingText = actionLabel + `... (${actionElapsed}초)`;
            }, 1000);
            scrollToBottom();
            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 120000);
                const response = await fetch('/api/ask', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        prompt: msg.prompt,
                        action: action,
                        profile_name: msg.profileName,
                    }),
                    signal: controller.signal,
                });
                clearTimeout(timeoutId);

                const data = await response.json();
                if (data.success) {
                    msg.cachedActions[action] = data.result;
                    processResult(msg, action, data.result);
                    msg.action = action;
                    if (data.elapsed_ms) msg.elapsed_ms = data.elapsed_ms;
                } else {
                    showToast(data.error || '오류가 발생했습니다.', 'error');
                }
            } catch (err) {
                if (err.name === 'AbortError') {
                    showToast('요청 시간이 초과되었습니다 (120초).', 'error');
                } else {
                    showToast('서버 연결에 실패했습니다.', 'error');
                }
            } finally {
                clearInterval(actionTimer);
                msg.actionLoading = false;
                msg.actionLoadingText = '';
                scrollToBottom();
            }
        }

        function renderChart(msgIdx) {
            const msg = messages.value[msgIdx];
            if (!msg || !msg.tableData || msg.tableData.length === 0) return;

            nextTick(() => {
                const canvasElements = document.querySelectorAll(`canvas[data-v-chart="${msgIdx}"]`);
                let canvas = canvasElements.length > 0 ? canvasElements[0] : null;

                if (!canvas) {
                    const allCanvas = document.querySelectorAll('canvas');
                    for (const c of allCanvas) {
                        if (c.closest('.message-bubble')?.contains(c)) {
                            const messageElements = document.querySelectorAll('.message-assistant');
                            const msgElement = messageElements[msgIdx];
                            if (msgElement && msgElement.contains(c)) {
                                canvas = c;
                                break;
                            }
                        }
                    }
                }

                if (!canvas) return;

                if (chartInstances[msgIdx]) {
                    chartInstances[msgIdx].destroy();
                }

                const data = msg.tableData;
                const columns = Object.keys(data[0]);

                let labelCol = columns[0];
                let valueCol = columns.length > 1 ? columns[1] : columns[0];

                for (const col of columns) {
                    if (typeof data[0][col] === 'string' || isNaN(Number(data[0][col]))) {
                        labelCol = col;
                        break;
                    }
                }

                for (const col of columns) {
                    if (col !== labelCol && !isNaN(Number(data[0][col]))) {
                        valueCol = col;
                        break;
                    }
                }

                const labels = data.map(row => String(row[labelCol]));
                const values = data.map(row => Number(row[valueCol]) || 0);

                const colors = [
                    '#C74634', '#2563eb', '#16a34a', '#d97706', '#7c3aed',
                    '#db2777', '#0891b2', '#65a30d', '#dc2626', '#4f46e5',
                ];

                const bgColors = msg.chartType === 'pie'
                    ? colors.slice(0, values.length)
                    : 'rgba(199, 70, 52, 0.7)';

                const borderColors = msg.chartType === 'pie'
                    ? colors.slice(0, values.length)
                    : '#C74634';

                chartInstances[msgIdx] = new Chart(canvas, {
                    type: msg.chartType,
                    data: {
                        labels: labels,
                        datasets: [{
                            label: valueCol,
                            data: values,
                            backgroundColor: bgColors,
                            borderColor: borderColors,
                            borderWidth: msg.chartType === 'pie' ? 2 : 1,
                        }],
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: true,
                        plugins: {
                            legend: {
                                display: msg.chartType === 'pie',
                            },
                        },
                    },
                });
            });
        }

        // === Vector Search Methods ===

        // --- Step 1: Table Management ---

        async function dropVectorTables() {
            if (!confirm('Vector Store 테이블(documents, doc_chunks)을 삭제합니다. 모든 데이터가 손실됩니다. 계속하시겠습니까?')) return;
            tableActionLoading.value = true;
            tableActionResult.value = null;
            try {
                const response = await fetch('/api/vector/drop-tables', { method: 'POST' });
                const data = await response.json();
                tableActionResult.value = {
                    action: 'drop',
                    success: data.success,
                    tables: data.tables || [],
                    sql_executed: data.sql_executed || '',
                    error: data.error || null,
                };
                if (data.success) {
                    showToast('테이블이 삭제되었습니다.');
                    uploadedDocs.value = [];
                } else {
                    showToast(data.error || '삭제에 실패했습니다.', 'error');
                }
            } catch (err) {
                tableActionResult.value = { action: 'drop', success: false, error: err.message };
                showToast('서버 연결에 실패했습니다.', 'error');
            } finally {
                tableActionLoading.value = false;
            }
        }

        async function createVectorTables() {
            tableActionLoading.value = true;
            tableActionResult.value = null;
            try {
                const response = await fetch('/api/vector/create-tables', { method: 'POST' });
                const data = await response.json();
                tableActionResult.value = {
                    action: 'create',
                    success: data.success,
                    tables: data.tables || [],
                    created: data.created || [],
                    existing: data.existing || [],
                    sql_executed: data.sql_executed || '',
                    error: data.error || null,
                };
                if (data.success) {
                    const msg = (data.created && data.created.length > 0)
                        ? `테이블 생성 완료: ${data.created.join(', ')}`
                        : '기존 테이블에 연결되었습니다.';
                    showToast(msg);
                } else {
                    showToast(data.error || '생성에 실패했습니다.', 'error');
                }
            } catch (err) {
                tableActionResult.value = { action: 'create', success: false, error: err.message };
                showToast('서버 연결에 실패했습니다.', 'error');
            } finally {
                tableActionLoading.value = false;
            }
        }

        // --- Step 2: Table Inspection ---

        async function fetchTableDefinition() {
            tableDefLoading.value = true;
            tableDefResult.value = null;
            try {
                const response = await fetch('/api/vector/table-definition', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ table_name: tableInspectTarget.value }),
                });
                const data = await response.json();
                tableDefResult.value = data;
            } catch (err) {
                tableDefResult.value = { success: false, error: err.message };
            } finally {
                tableDefLoading.value = false;
            }
        }

        async function fetchTableData() {
            tableDataLoading.value = true;
            tableDataResult.value = null;
            try {
                const response = await fetch('/api/vector/table-data', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ table_name: tableInspectTarget.value, limit: 50 }),
                });
                const data = await response.json();
                tableDataResult.value = data;
            } catch (err) {
                tableDataResult.value = { success: false, error: err.message };
            } finally {
                tableDataLoading.value = false;
            }
        }

        async function fetchTableIndexes() {
            tableIdxLoading.value = true;
            tableIdxResult.value = null;
            try {
                const response = await fetch('/api/vector/table-indexes', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ table_name: tableInspectTarget.value }),
                });
                const data = await response.json();
                tableIdxResult.value = data;
            } catch (err) {
                tableIdxResult.value = { success: false, error: err.message };
            } finally {
                tableIdxLoading.value = false;
            }
        }

        // --- Step 4: Query Inspection ---

        async function fetchRecentSql() {
            recentSqlLoading.value = true;
            recentSqlResult.value = null;
            try {
                const response = await fetch('/api/vector/recent-queries');
                const data = await response.json();
                recentSqlResult.value = data;
            } catch (err) {
                recentSqlResult.value = { success: false, error: err.message };
            } finally {
                recentSqlLoading.value = false;
            }
        }

        async function fetchExplainPlan() {
            explainPlanLoading.value = true;
            explainPlanResult.value = null;
            try {
                const response = await fetch('/api/vector/explain-plan', { method: 'POST' });
                const data = await response.json();
                explainPlanResult.value = data;
            } catch (err) {
                explainPlanResult.value = { success: false, error: err.message };
            } finally {
                explainPlanLoading.value = false;
            }
        }

        // --- Upload & Search (existing) ---

        async function handleFileSelect(event) {
            const file = event.target.files[0];
            if (file) {
                await uploadDocument(file);
            }
            event.target.value = '';
        }

        async function handleFileDrop(event) {
            dragOver.value = false;
            const file = event.dataTransfer.files[0];
            if (file && file.name.toLowerCase().endsWith('.pdf')) {
                await uploadDocument(file);
            } else {
                showToast('PDF 파일만 업로드 가능합니다.', 'error');
            }
        }

        async function uploadDocument(file) {
            if (file.size > 10 * 1024 * 1024) {
                showToast('파일 크기가 10MB를 초과합니다.', 'error');
                return;
            }

            isUploading.value = true;
            const formData = new FormData();
            formData.append('file', file);

            try {
                const response = await fetch('/api/vector/upload', {
                    method: 'POST',
                    body: formData,
                });

                const data = await response.json();
                if (data.success) {
                    showToast(`${data.filename}: ${data.chunks_count}개 청크 처리 완료`);
                    await fetchDocuments();
                } else {
                    showToast(data.error || '업로드에 실패했습니다.', 'error');
                }
            } catch (err) {
                showToast('업로드 중 오류가 발생했습니다: ' + err.message, 'error');
            } finally {
                isUploading.value = false;
            }
        }

        async function fetchDocuments() {
            try {
                const response = await fetch('/api/vector/documents');
                const data = await response.json();
                if (data.success) {
                    uploadedDocs.value = data.documents;
                }
            } catch (err) {
                // 조용히 실패
            }
        }

        async function deleteDoc(docId) {
            try {
                const response = await fetch(`/api/vector/documents/${docId}`, { method: 'DELETE' });
                const data = await response.json();
                if (data.success) {
                    showToast('문서가 삭제되었습니다.');
                    await fetchDocuments();
                } else {
                    showToast(data.error || '삭제에 실패했습니다.', 'error');
                }
            } catch (err) {
                showToast('삭제 중 오류가 발생했습니다.', 'error');
            }
        }

        async function sendVectorQuestion() {
            const query = vectorInput.value.trim();
            if (!query || vectorLoading.value) return;

            const mode = vectorSearchMode.value;
            const profileName = selectedProfile.value;

            vectorMessages.value.push({
                role: 'user',
                content: query,
                timestamp: formatTime(),
            });

            vectorInput.value = '';

            const assistantMsg = reactive({
                role: 'assistant',
                mode: mode,
                query: query,
                loading: true,
                loadingText: vectorLoadingMessages[0],
                answer: null,
                chunks: null,
                sql_executed: null,
                sqlExpanded: false,
                error: null,
                elapsed_ms: null,
                embeddingInfo: null,
                indexInfo: null,
                keywordCompare: null,
                keywordResults: null,
                vectorResults: null,
                timestamp: formatTime(),
            });
            vectorMessages.value.push(assistantMsg);
            scrollVectorToBottom();

            vectorLoading.value = true;
            let loadIdx = 0;
            const loadingInterval = setInterval(() => {
                loadIdx = (loadIdx + 1) % vectorLoadingMessages.length;
                assistantMsg.loadingText = vectorLoadingMessages[loadIdx];
            }, 1500);

            try {
                const response = await fetch('/api/vector/search', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        query: query,
                        mode: mode,
                        top_k: 5,
                        profile_name: profileName,
                    }),
                });

                const data = await response.json();
                clearInterval(loadingInterval);

                if (data.success) {
                    assistantMsg.elapsed_ms = data.elapsed_ms;

                    if (mode === 'compare') {
                        assistantMsg.keywordResults = data.keyword_results;
                        assistantMsg.vectorResults = data.vector_results;
                    } else {
                        assistantMsg.answer = data.answer;
                        assistantMsg.chunks = data.chunks;
                        assistantMsg.sql_executed = data.sql_executed;
                    }
                } else {
                    assistantMsg.error = data.error || '검색에 실패했습니다.';
                }
            } catch (err) {
                clearInterval(loadingInterval);
                assistantMsg.error = '서버 연결에 실패했습니다: ' + err.message;
            } finally {
                assistantMsg.loading = false;
                vectorLoading.value = false;
                scrollVectorToBottom();
            }
        }

        async function showEmbeddingInfo(msgIdx) {
            const msg = vectorMessages.value[msgIdx];
            if (!msg || !msg.query) return;

            if (msg.embeddingInfo) {
                msg.embeddingInfo = null;
                return;
            }

            try {
                const response = await fetch('/api/vector/embedding-info', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: msg.query }),
                });
                const data = await response.json();
                if (data.success) {
                    msg.embeddingInfo = data;
                } else {
                    showToast(data.error || '임베딩 정보 조회 실패', 'error');
                }
            } catch (err) {
                showToast('서버 연결에 실패했습니다.', 'error');
            }
            scrollVectorToBottom();
        }

        async function showIndexInfo(msgIdx) {
            const msg = vectorMessages.value[msgIdx];
            if (!msg) return;

            if (msg.indexInfo) {
                msg.indexInfo = null;
                return;
            }

            try {
                const response = await fetch('/api/vector/index-info');
                const data = await response.json();
                if (data.success) {
                    msg.indexInfo = data;
                } else {
                    showToast(data.error || '인덱스 정보 조회 실패', 'error');
                }
            } catch (err) {
                showToast('서버 연결에 실패했습니다.', 'error');
            }
            scrollVectorToBottom();
        }

        async function doKeywordCompare(msgIdx) {
            const msg = vectorMessages.value[msgIdx];
            if (!msg || !msg.query) return;

            if (msg.keywordCompare) {
                msg.keywordCompare = null;
                return;
            }

            try {
                const response = await fetch('/api/vector/search', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        query: msg.query,
                        mode: 'keyword',
                        top_k: 5,
                        profile_name: selectedProfile.value,
                    }),
                });
                const data = await response.json();
                if (data.success) {
                    msg.keywordCompare = {
                        chunks: data.chunks,
                        match_count: data.match_count,
                        sql_executed: data.sql_executed,
                    };
                } else {
                    showToast(data.error || '키워드 검색 실패', 'error');
                }
            } catch (err) {
                showToast('서버 연결에 실패했습니다.', 'error');
            }
            scrollVectorToBottom();
        }

        // === Init ===
        async function checkHealth() {
            try {
                const response = await fetch('/api/health');
                const data = await response.json();
                dbConnected.value = data.database_connected;
                schema.value = data.schema || '';
            } catch {
                dbConnected.value = false;
            }
        }

        async function loadProfiles() {
            try {
                const response = await fetch('/api/profiles');
                const data = await response.json();
                if (data.success && data.profiles.length > 0) {
                    profiles.value = data.profiles;
                    if (!selectedProfile.value) {
                        // GROQ_SH_PROFILE 우선 선택, 없으면 첫 번째 프로필
                        const defaultProfile = data.profiles.find(p => p.profile_name === 'GROQ_SH_PROFILE');
                        selectedProfile.value = defaultProfile ? defaultProfile.profile_name : data.profiles[0].profile_name;
                        updateExampleQuestions(selectedProfile.value);
                        await callSetProfile(selectedProfile.value);
                        loadSchemaInfo(selectedProfile.value);
                    }
                } else {
                    profiles.value = [];
                    showToast('DB에 등록된 AI 프로필이 없습니다.', 'error');
                }
            } catch (err) {
                profiles.value = [];
                showToast('프로필 목록 조회 실패: ' + err.message, 'error');
            }
        }

        async function callSetProfile(profileName) {
            try {
                const response = await fetch('/api/set-profile', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ profile_name: profileName }),
                });
                const data = await response.json();
                if (data.success) {
                    // 프로필 상세 속성을 메인 창에 메시지로 표시
                    profileInfo.value = data.attributes || null;

                    messages.value.push({
                        role: 'assistant',
                        action: 'profile',
                        loading: false,
                        profileResult: {
                            profile_name: profileName,
                            attributes: data.attributes || null,
                        },
                        timestamp: formatTime(),
                    });
                    scrollToBottom();
                    showToast(`프로필 설정 완료: ${profileName}`);
                } else {
                    showToast(data.error || '프로필 설정 실패', 'error');
                }
            } catch (err) {
                showToast('프로필 설정 실패: ' + err.message, 'error');
            }
        }

        function updateExampleQuestions(profileName) {
            const upper = (profileName || '').toUpperCase();
            if (upper.includes('SSB')) {
                exampleQuestions.value = exampleQuestionsMap.SSB;
            } else if (upper.includes('SH')) {
                exampleQuestions.value = exampleQuestionsMap.SH;
            } else {
                exampleQuestions.value = exampleQuestionsMap.DEFAULT;
            }
        }

        async function loadSchemaInfo(profileName) {
            schemaLoading.value = true;
            schemaInfo.value = null;
            schemaExpanded.value = {};
            try {
                const response = await fetch('/api/schema-info', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ profile_name: profileName }),
                });
                const data = await response.json();
                if (data.success) {
                    schemaInfo.value = data.tables || [];
                    if (data.tables && data.tables.length === 0 && data.error) {
                        console.warn('Schema info:', data.error);
                    }
                } else {
                    console.error('Schema info error:', data.error);
                    schemaInfo.value = [];
                }
            } catch (err) {
                console.error('Schema info fetch error:', err);
                schemaInfo.value = [];
            } finally {
                schemaLoading.value = false;
            }
        }

        function toggleSchemaTable(tableName) {
            schemaExpanded.value[tableName] = !schemaExpanded.value[tableName];
        }

        function getAnnotationSet() {
            const profile = (selectedProfile.value || '').toUpperCase();
            if (profile.includes('SH')) return { owner: 'ADMIN', tables: annotationSets.SH };
            return null;
        }

        async function applyAnnotations() {
            const info = getAnnotationSet();
            if (!info) {
                showToast('현재 프로필에 해당하는 Annotation 세트가 없습니다.', 'error');
                return;
            }
            // 각 테이블에 _owner 주입
            const annoSet = {};
            for (const [tbl, cols] of Object.entries(info.tables)) {
                annoSet[tbl] = { ...cols, _owner: info.owner };
            }
            annotationApplying.value = true;
            try {
                const response = await fetch('/api/apply-annotations', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ annotation_set: annoSet }),
                });
                const data = await response.json();
                if (data.success) {
                    if (data.applied_count > 0) {
                        showToast(`Annotation 적용 완료 (${data.applied_count}건${data.error_count > 0 ? ', 실패 ' + data.error_count + '건' : ''})`);
                    } else {
                        const errMsg = data.errors && data.errors.length > 0 ? data.errors[0] : '적용된 항목 없음';
                        showToast('Annotation 적용 실패: ' + errMsg, 'error');
                    }
                    if (data.error_count > 0) {
                        console.error('Annotation errors:', data.errors);
                    }
                    await loadSchemaInfo(selectedProfile.value);
                } else {
                    showToast('Annotation 적용 실패: ' + (data.error || ''), 'error');
                }
            } catch (err) {
                showToast('Annotation 적용 실패: ' + err.message, 'error');
            } finally {
                annotationApplying.value = false;
            }
        }

        async function removeAnnotations() {
            const info = getAnnotationSet();
            if (!info) {
                showToast('현재 프로필에 해당하는 Annotation 세트가 없습니다.', 'error');
                return;
            }
            annotationRemoving.value = true;
            try {
                const tableNames = Object.keys(info.tables);
                const response = await fetch('/api/remove-annotations', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ table_names: tableNames, owner: info.owner }),
                });
                const data = await response.json();
                if (data.success) {
                    showToast(`Annotation 제거 완료 (${data.removed_count}건)`);
                    await loadSchemaInfo(selectedProfile.value);
                } else {
                    showToast('Annotation 제거 실패: ' + (data.error || ''), 'error');
                }
            } catch (err) {
                showToast('Annotation 제거 실패: ' + err.message, 'error');
            } finally {
                annotationRemoving.value = false;
            }
        }

        async function onProfileChange() {
            if (selectedProfile.value) {
                updateExampleQuestions(selectedProfile.value);
                await callSetProfile(selectedProfile.value);
                loadSchemaInfo(selectedProfile.value);
            }
        }

        // === AWR Analyzer Methods ===

        const awrScoreColor = computed(() => {
            const score = awrAnalysis.value?.overallScore || 0;
            if (score >= 80) return '#28a745';
            if (score >= 60) return '#ffc107';
            if (score >= 40) return '#fd7e14';
            return '#dc3545';
        });

        const awrScoreDash = computed(() => {
            const score = awrAnalysis.value?.overallScore || 0;
            const circumference = 2 * Math.PI * 50;
            const filled = (score / 100) * circumference;
            return `${filled} ${circumference}`;
        });

        function awrSnapshotLabel(key) {
            const labels = {
                dbName: 'DB Name',
                instanceName: 'Instance',
                startTime: '시작 시간',
                endTime: '종료 시간',
                elapsed: '경과 시간',
                dbTime: 'DB Time',
                isExadata: 'Exadata',
            };
            return labels[key] || key;
        }

        async function handleAwrFileSelect(event) {
            const file = event.target.files[0];
            if (file) {
                await analyzeAwrFile(file);
            }
            event.target.value = '';
        }

        function handleAwrFileDrop(event) {
            awrDragOver.value = false;
            const file = event.dataTransfer.files[0];
            if (file && /\.(html?|htm)$/i.test(file.name)) {
                analyzeAwrFile(file);
            } else {
                showToast('HTML 파일만 업로드 가능합니다.', 'error');
            }
        }

        async function analyzeAwrFile(file) {
            if (file.size > 20 * 1024 * 1024) {
                showToast('파일 크기가 20MB를 초과합니다.', 'error');
                return;
            }

            awrLoading.value = true;
            awrError.value = '';
            awrAnalysis.value = null;
            awrFollowupMessages.value = [];

            const formData = new FormData();
            formData.append('file', file);
            if (awrProfileName.value) {
                formData.append('profile_name', awrProfileName.value);
            }

            const controller = new AbortController();
            const timeout = setTimeout(() => controller.abort(), 180000);

            try {
                const response = await fetch('/api/awr/analyze', {
                    method: 'POST',
                    body: formData,
                    signal: controller.signal,
                });
                const data = await response.json();
                clearTimeout(timeout);

                if (data.success) {
                    awrAnalysis.value = data.analysis;
                    awrSessionId.value = data.session_id;
                    awrFilename.value = data.filename;
                    awrParseInfo.value = data.parse_info;
                    awrElapsedMs.value = data.elapsed_ms;
                    extraSubMenu.value = 'awr-result';
                    showToast('AWR 분석이 완료되었습니다.', 'success');
                } else {
                    awrError.value = data.error || '분석에 실패했습니다.';
                }
            } catch (err) {
                clearTimeout(timeout);
                if (err.name === 'AbortError') {
                    awrError.value = '분석 시간이 초과되었습니다. (3분)';
                } else {
                    awrError.value = err.message;
                }
            } finally {
                awrLoading.value = false;
            }
        }

        async function sendAwrFollowup() {
            const question = awrFollowupInput.value.trim();
            if (!question || awrFollowupLoading.value) return;

            awrFollowupMessages.value.push({ role: 'user', content: question });
            awrFollowupInput.value = '';

            const assistantMsg = { role: 'assistant', content: '', loading: true };
            awrFollowupMessages.value.push(assistantMsg);
            awrFollowupLoading.value = true;

            try {
                const response = await fetch('/api/awr/followup', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        question: question,
                        session_id: awrSessionId.value,
                        profile_name: awrProfileName.value,
                    }),
                });
                const data = await response.json();
                assistantMsg.loading = false;

                if (data.success) {
                    assistantMsg.content = data.answer;
                } else {
                    assistantMsg.content = '오류: ' + (data.error || '응답 생성에 실패했습니다.');
                }
            } catch (err) {
                assistantMsg.loading = false;
                assistantMsg.content = '오류: ' + err.message;
            } finally {
                awrFollowupLoading.value = false;
                await nextTick();
                const el = document.querySelector('.awr-followup-messages');
                if (el) el.scrollTop = el.scrollHeight;
            }
        }

        onMounted(() => {
            checkHealth();
            loadProfiles();
            fetchDocuments();
        });

        return {
            // Common
            activeTab,
            dbConnected,
            schema,
            profiles,
            selectedProfile,
            onProfileChange,
            profileInfo,
            schemaInfo,
            schemaLoading,
            schemaExpanded,
            toggleSchemaTable,
            annotationApplying,
            annotationRemoving,
            applyAnnotations,
            removeAnnotations,
            toast,
            highlightOracleSQL,
            highlightSQLWithLines,

            // NL2SQL
            userInput,
            sqlInput,
            isLoading,
            isSqlLoading,
            selectedAction,
            messages,
            chatMessages,
            actionModesLeft,
            actionModesRight,
            exampleQuestions,
            setPrompt,
            sendQuestion,
            executeSql,
            getActionButtons,
            executeAction,
            renderChart,

            // Vector Search
            vectorSubMenu,
            vectorInput,
            vectorLoading,
            vectorSearchMode,
            vectorMessages,
            vectorChatMessages,
            uploadedDocs,
            isUploading,
            dragOver,
            vectorExampleQuestions,
            handleFileSelect,
            handleFileDrop,
            deleteDoc,
            sendVectorQuestion,
            showEmbeddingInfo,
            showIndexInfo,
            doKeywordCompare,

            // Step 1: Table Management
            tableActionLoading,
            tableActionResult,
            dropVectorTables,
            createVectorTables,

            // Step 2: Table Inspection
            tableInspectTarget,
            tableDefResult,
            tableDataResult,
            tableIdxResult,
            tableDefLoading,
            tableDataLoading,
            tableIdxLoading,
            fetchTableDefinition,
            fetchTableData,
            fetchTableIndexes,

            // Step 4: Query Inspection
            recentSqlResult,
            explainPlanResult,
            recentSqlLoading,
            explainPlanLoading,
            fetchRecentSql,
            fetchExplainPlan,

            // AWR Analyzer
            extraSubMenu,
            awrProfileName,
            awrLoading,
            awrError,
            awrAnalysis,
            awrFilename,
            awrParseInfo,
            awrElapsedMs,
            awrSessionId,
            awrDragOver,
            awrFollowupInput,
            awrFollowupLoading,
            awrFollowupMessages,
            awrScoreColor,
            awrScoreDash,
            awrSnapshotLabel,
            handleAwrFileSelect,
            handleAwrFileDrop,
            sendAwrFollowup,
        };
    },
});

app.mount('#app');
