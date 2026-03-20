const { createApp, ref, reactive, nextTick, onMounted, computed } = Vue;

const app = createApp({
    delimiters: ['[[', ']]'],

    setup() {
        // === State ===
        const userInput = ref('');
        const isLoading = ref(false);
        const dbConnected = ref(false);
        const schema = ref('');
        const selectedProfile = ref('{{ default_profile }}');
        const selectedAction = ref('runsql');
        const profiles = ref([]);
        const messages = reactive([]);
        const chatMessages = ref(null);
        const chartInstances = {};

        const toast = reactive({
            show: false,
            message: '',
            type: 'success',
        });

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

        const exampleQuestions = reactive([
            '매출 상위 5개 제품',
            '월별 매출 추이',
            '국가별 고객 수',
            '연도별 총 매출액',
            '채널별 주문 건수',
        ]);

        const loadingMessages = [
            '자연어 분석 중...',
            'SQL 생성 중...',
            '쿼리 실행 중...',
            '결과 정리 중...',
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

        // === Methods ===

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

        function getActionButtons(msg) {
            const rules = actionButtonRules[msg.action] || [];
            return rules.filter(btn => {
                // 차트 버튼은 테이블 데이터가 있을 때만
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

            // 사용자 메시지 추가
            messages.push({
                role: 'user',
                content: prompt,
                timestamp: formatTime(),
            });

            userInput.value = '';

            // AI 응답 placeholder
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
            messages.push(assistantMsg);
            scrollToBottom();

            // 로딩 메시지 순환
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
                    // JSON 문자열이면 파싱 시도
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
                // narrate, explainsql, showprompt, summarize, chat
                msg.textResult = typeof result === 'string' ? result : JSON.stringify(result, null, 2);
            }
        }

        async function executeAction(msgIdx, action) {
            const msg = messages[msgIdx];
            if (!msg || msg.actionLoading) return;

            // 차트 토글
            if (action === 'chart') {
                msg.showChart = !msg.showChart;
                if (msg.showChart) {
                    nextTick(() => renderChart(msgIdx));
                }
                return;
            }

            // 피드백 토글
            if (action === 'feedback') {
                msg.showFeedback = !msg.showFeedback;
                return;
            }

            // 캐시된 결과 확인
            if (msg.cachedActions && msg.cachedActions[action]) {
                processResult(msg, action, msg.cachedActions[action]);
                msg.action = action;
                scrollToBottom();
                return;
            }

            // API 호출
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
            const msg = messages[msgIdx];
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
            const msg = messages[msgIdx];
            if (!msg || !msg.tableData || msg.tableData.length === 0) return;

            const refKey = 'chart-' + msgIdx;

            // nextTick을 사용하여 canvas가 렌더링될 때까지 대기
            nextTick(() => {
                // $refs 대신 DOM에서 직접 canvas를 찾음
                const canvasElements = document.querySelectorAll(`canvas[data-v-chart="${msgIdx}"]`);
                let canvas = canvasElements.length > 0 ? canvasElements[0] : null;

                // data 속성이 없으면 ref 이름으로 시도
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

                // 기존 차트 파괴
                if (chartInstances[msgIdx]) {
                    chartInstances[msgIdx].destroy();
                }

                const data = msg.tableData;
                const columns = Object.keys(data[0]);

                // X축: 첫 번째 문자열 컬럼, Y축: 첫 번째 숫자 컬럼
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
                } else {
                    // 프로필 조회 실패 시 기본값
                    profiles.value = [{ profile_name: selectedProfile.value, status: 'ENABLED' }];
                }
            } catch {
                profiles.value = [{ profile_name: selectedProfile.value, status: 'ENABLED' }];
            }
        }

        onMounted(() => {
            checkHealth();
            loadProfiles();
        });

        return {
            userInput,
            isLoading,
            dbConnected,
            schema,
            selectedProfile,
            selectedAction,
            profiles,
            messages,
            chatMessages,
            toast,
            actionModes,
            exampleQuestions,
            setPrompt,
            sendQuestion,
            getActionButtons,
            executeAction,
            submitFeedback,
            renderChart,
        };
    },
});

app.mount('#app');
