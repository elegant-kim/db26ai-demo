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
        const isLoading = ref(false);
        const selectedAction = ref('runsql');
        const messages = ref([]);
        const chatMessages = ref(null);
        const chartInstances = {};

        // === Vector Search State ===
        const vectorInput = ref('');
        const vectorLoading = ref(false);
        const vectorSearchMode = ref('vector');
        const vectorMessages = ref([]);
        const vectorChatMessages = ref(null);
        const uploadedDocs = ref([]);
        const isUploading = ref(false);
        const dragOver = ref(false);

        // === Constants ===
        const actionModes = [
            { value: 'runsql', label: '실행' },
            { value: 'showsql', label: 'SQL 보기' },
            { value: 'narrate', label: '설명' },
            { value: 'explainsql', label: 'SQL 해설' },
            { value: 'showprompt', label: '프롬프트' },
            { value: 'summarize', label: '요약' },
            { value: 'chat', label: '대화' },
        ];

        const exampleQuestions = ref([
            '매출 상위 5개 제품을 알려주세요',
            '월별 매출 추이를 알려주세요',
            '국가별 고객 수를 알려주세요',
            '연도별 총 매출액을 알려주세요',
            '채널별 주문 건수를 알려주세요',
        ]);

        const vectorExampleQuestions = ref([
            '연차 사용 규정을 알려주세요',
            '퇴직금 산정 기준을 알려주세요',
            '출장비 정산 절차를 알려주세요',
        ]);

        const loadingMessages = [
            '자연어 분석 중...',
            'SQL 생성 중...',
            '쿼리 실행 중...',
            '결과 정리 중...',
        ];

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
                { action: 'showprompt', label: '프롬프트 보기' },
                { action: 'summarize', label: '요약' },
                { action: 'feedback', label: '피드백 제출' },
            ],
            showsql: [
                { action: 'runsql', label: '실행' },
                { action: 'narrate', label: '설명' },
                { action: 'explainsql', label: 'SQL 해설' },
                { action: 'showprompt', label: '프롬프트 보기' },
                { action: 'feedback', label: '피드백 제출' },
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
            // Escape HTML first
            let s = sql.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

            // Oracle-specific functions (Oracle Red)
            s = s.replace(/\b(VECTOR_DISTANCE|VECTOR_EMBEDDING|DBMS_VECTOR_CHAIN\.UTL_TO_CHUNKS|DBMS_CLOUD_AI\.GENERATE)\b/g,
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
                'VECTOR', 'CLOB', 'NUMBER', 'VARCHAR2', 'TIMESTAMP', 'IDENTITY', 'PRIMARY KEY'];
            for (const kw of keywords) {
                const regex = new RegExp(`\\b(${kw})\\b`, 'gi');
                s = s.replace(regex, (match) => {
                    // Don't re-color if already inside a span
                    return `<span style="color: #7c3aed;">${match}</span>`;
                });
            }

            return s;
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

            messages.value.push({
                role: 'user',
                content: prompt,
                timestamp: formatTime(),
            });

            userInput.value = '';

            const assistantMsg = reactive({
                role: 'assistant',
                action: action,
                prompt: prompt,
                profileName: profileName,
                loading: true,
                loadingText: loadingMessages[0],
                sql: null,
                tableData: null,
                textResult: null,
                error: null,
                elapsed_ms: null,
                showChart: false,
                chartType: 'bar',
                sqlExpanded: true,
                showFeedback: false,
                feedbackText: '',
                actionLoading: false,
                cachedActions: {},
                timestamp: formatTime(),
            });
            messages.value.push(assistantMsg);
            scrollToBottom();

            isLoading.value = true;
            let loadIdx = 0;
            const loadingInterval = setInterval(() => {
                loadIdx = (loadIdx + 1) % loadingMessages.length;
                assistantMsg.loadingText = loadingMessages[loadIdx];
            }, 1500);

            try {
                const response = await fetch('/api/ask', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt, action, profile_name: profileName }),
                });

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
                assistantMsg.error = '서버 연결에 실패했습니다: ' + err.message;
            } finally {
                assistantMsg.loading = false;
                isLoading.value = false;
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

            if (action === 'feedback') {
                msg.showFeedback = !msg.showFeedback;
                return;
            }

            if (msg.cachedActions && msg.cachedActions[action]) {
                processResult(msg, action, msg.cachedActions[action]);
                msg.action = action;
                scrollToBottom();
                return;
            }

            msg.actionLoading = true;
            try {
                const response = await fetch('/api/ask', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        prompt: msg.prompt,
                        action: action,
                        profile_name: msg.profileName,
                    }),
                });

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
                showToast('서버 연결에 실패했습니다.', 'error');
            } finally {
                msg.actionLoading = false;
                scrollToBottom();
            }
        }

        async function submitFeedback(msgIdx) {
            const msg = messages.value[msgIdx];
            if (!msg || !msg.feedbackText) return;

            try {
                const response = await fetch('/api/feedback', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        prompt: msg.prompt,
                        feedback: msg.feedbackText,
                        profile_name: msg.profileName,
                    }),
                });

                const data = await response.json();
                if (data.success) {
                    showToast('피드백이 제출되었습니다.');
                    msg.showFeedback = false;
                    msg.feedbackText = '';
                } else {
                    showToast(data.error || '피드백 제출에 실패했습니다.', 'error');
                }
            } catch (err) {
                showToast('서버 연결에 실패했습니다.', 'error');
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
                // compare mode
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
                        selectedProfile.value = data.profiles[0].profile_name;
                    }
                } else {
                    profiles.value = [{ profile_name: 'GROQ_PROFILE', status: 'ENABLED' }];
                    selectedProfile.value = 'GROQ_PROFILE';
                }
            } catch {
                profiles.value = [{ profile_name: 'GROQ_PROFILE', status: 'ENABLED' }];
                selectedProfile.value = 'GROQ_PROFILE';
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
            toast,
            highlightOracleSQL,

            // NL2SQL
            userInput,
            isLoading,
            selectedAction,
            messages,
            chatMessages,
            actionModes,
            exampleQuestions,
            setPrompt,
            sendQuestion,
            getActionButtons,
            executeAction,
            submitFeedback,
            renderChart,

            // Vector Search
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
        };
    },
});

app.mount('#app');
