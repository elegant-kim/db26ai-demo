<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Cpu, Boxes, UploadCloud, Cloud } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'
import SearchableSelect from '@/components/ui/SearchableSelect.vue'
import Segmented from '@/components/demo/Segmented.vue'
import KvGrid from '@/components/demo/KvGrid.vue'
import SqlBlock from '@/components/demo/SqlBlock.vue'
import { ONNX_LOAD_PLSQL } from '@/lib/vector'
import { fmtNum } from '@/lib/format'
import { useSystemStore } from '@/stores/system'
import { useVectorStore } from '@/stores/vector'

const v = useVectorStore()
const system = useSystemStore()
onMounted(() => { void v.loadConfig() })

const SOURCES = [{ value: 'database', label: 'DB 내장 (ONNX)', hint: 'VECTOR_EMBEDDING() — 외부 API 없음' }, { value: 'external', label: '외부 API', hint: 'OpenAI 호환 임베딩 API' }]
const pendingSource = ref<'database' | 'external' | null>(null)
const askReset = ref(false)
const switching = ref(false)
async function confirmSource() {
  if (!pendingSource.value) return
  switching.value = true
  try { await v.applySource(pendingSource.value); askReset.value = true } catch (e: any) { system.toast(e?.message || '설정 변경 실패', 'error') }
  finally { switching.value = false; pendingSource.value = null }
}
const modelOptions = computed(() => v.onnxModels.map((m) => ({ value: m.model_name, label: m.model_name, sub: m.creation_date })))
const configKv = computed(() => ({
  '소스': v.source === 'database' ? 'VECTOR_EMBEDDING() — DB 내장 ONNX' : 'External API', '모델': v.model || '—',
  ...(v.source === 'external' ? { 'API URL': v.apiUrl || '(미설정)', 'API 키': v.apiKeySet ? '설정됨' : '없음' } : {}),
  '인덱스 모델': v.indexInfo?.embedding_model ?? '—', '인덱스 차원': v.indexInfo?.vector_dimensions ?? '—', '임베딩된 청크': `${v.indexInfo?.embedded_chunks ?? '—'} / ${v.indexInfo?.total_chunks ?? '—'}`,
}))
const testKv = computed(() => v.onnxTest && v.onnxTest.success ? { '모델': v.onnxTest.model_name, '차원 수': v.onnxTest.dimensions, '처리 시간': `${v.onnxTest.processing_ms}ms`, '입력 텍스트': v.onnxTest.sample_text, '벡터 미리보기': v.onnxTest.vector_preview } : null)
const pendingDelete = ref<string | null>(null)

// 적재 — 로컬 / Object Storage
const fileInput = ref<HTMLInputElement | null>(null)
const over = ref(false)
const localFile = ref<File | null>(null)
const localName = ref('')
const cloudUri = ref(''); const cloudFile = ref(''); const cloudName = ref('')
function pickOnnx(files: FileList | null) {
  const f = files?.[0]; if (!f) return
  if (!/\.onnx$/i.test(f.name)) { system.toast('.onnx 파일만 올릴 수 있습니다.', 'error'); return }
  localFile.value = f
  if (!localName.value.trim()) localName.value = f.name.replace(/\.onnx$/i, '').replace(/[^a-zA-Z0-9_]/g, '_').toUpperCase()
}
</script>

<template>
  <div class="flex flex-col gap-5">
    <Card title="임베딩 설정" subtitle="임베딩을 DB 안 ONNX 로 할지 외부 API 로 할지, 어떤 모델을 쓸지. 검색과 업로드가 모두 이 설정을 따릅니다" :icon="Cpu">
      <template #actions><Segmented :model-value="v.source" :options="SOURCES" size="sm" @update:model-value="(s: string) => { if (s !== v.source) pendingSource = s as 'database' | 'external' }" /></template>
      <div v-if="v.dimensionWarning" class="mb-3 px-3 py-2.5 rounded-md text-sm" style="background: var(--accent-warm-soft); border-left: 3px solid var(--accent-warm); color: var(--text-primary);">⚠ {{ v.dimensionWarning }}</div>
      <div class="flex flex-wrap items-center gap-2 mb-3" v-if="v.source === 'database'">
        <span class="text-xs" style="color: var(--text-secondary);">DB 모델</span>
        <div class="w-[280px]"><SearchableSelect :model-value="v.model" :options="modelOptions" placeholder="ONNX 모델" :searchable="false" @update:model-value="(m: string) => m !== v.model && v.applyModel(m)" /></div>
        <Badge tone="info">{{ v.onnxModels.length }}개 등록</Badge>
      </div>
      <KvGrid :data="configKv" />
      <p class="text-xs mt-3 mb-0" style="color: var(--text-muted);">모델을 바꾸면 벡터 차원이 바뀝니다. <code class="font-mono">embedding VECTOR</code> 컬럼은 차원 무제약이지만 HNSW 인덱스가 첫 데이터의 차원으로 고정되므로, 바꾼 뒤에는 Vector Store 초기화 → 재업로드가 순서입니다 (ORA-51932 함정).</p>
    </Card>

    <Card title="ONNX 임베딩 모델 (USER_MINING_MODELS)" subtitle="DB 안에 적재된 모델 — 선택하면 임베딩 모델이 바뀌고, 테스트는 VECTOR_EMBEDDING 을 한 번 실행합니다" :icon="Boxes">
      <template #actions><Button variant="ghost" size="sm" :busy="v.onnxBusy === 'refresh'" @click="v.refreshOnnx()">새로고침</Button></template>
      <div v-if="v.onnxModels.length" class="rounded-md overflow-hidden" style="border: 1px solid var(--border-default);">
        <div v-for="m in v.onnxModels" :key="m.model_name" class="row flex flex-wrap items-center gap-3 px-3 py-2 text-sm" style="background: var(--bg-elevated);">
          <span class="font-mono font-semibold" style="color: var(--text-primary);">{{ m.model_name }}</span>
          <span class="text-xs" style="color: var(--text-muted);">{{ m.mining_function }} · {{ m.algorithm }} · {{ m.creation_date }}</span>
          <Badge :tone="m.model_name === v.model ? 'positive' : 'default'">{{ m.model_name === v.model ? '사용 중' : '미사용' }}</Badge>
          <span class="flex-1" />
          <Button v-if="m.model_name !== v.model && v.source === 'database'" size="sm" variant="secondary" @click="v.applyModel(m.model_name)">선택</Button>
          <Button size="sm" variant="secondary" :busy="v.onnxBusy === 'test' && v.onnxTest?.model_name === m.model_name" @click="v.testModel(m.model_name)">테스트</Button>
          <Button size="sm" variant="ghost" :disabled="m.model_name === v.model" @click="pendingDelete = m.model_name">삭제</Button>
        </div>
      </div>
      <p v-else class="text-sm m-0" style="color: var(--text-muted);">DB 에 등록된 ONNX 모델이 없습니다 — 아래에서 적재하세요.</p>
      <div v-if="v.onnxTest" class="mt-4 rounded-md p-3 flex flex-col gap-2" style="background: var(--bg-surface); border: 1px solid var(--border-default);">
        <div class="flex items-center justify-between"><span class="text-sm font-semibold" style="color: var(--text-primary);">테스트 결과 · {{ v.onnxTest.model_name }}</span><Button size="sm" variant="ghost" @click="v.onnxTest = null">닫기</Button></div>
        <div v-if="v.onnxTest.error" class="text-xs font-mono" style="color: var(--accent-negative);">{{ v.onnxTest.error }}</div>
        <template v-else-if="testKv"><KvGrid :data="testKv" /><SqlBlock :code="v.onnxTest.sql_executed" label="SQL" max-height="120px" /></template>
      </div>
    </Card>

    <div class="grid grid-cols-1 xl:grid-cols-2 gap-5">
      <Card title="로컬 .onnx 파일 적재" subtitle="파일을 서버가 받아 DBMS_VECTOR.LOAD_ONNX_MODEL 로 적재 (최대 3GB, 수 분)" :icon="UploadCloud">
        <div class="drop rounded-lg flex flex-col items-center justify-center gap-1 px-4 py-6 cursor-pointer text-center" :class="{ over }" @click="fileInput?.click()" @dragover.prevent="over = true" @dragleave="over = false" @drop.prevent="over = false; pickOnnx($event.dataTransfer?.files ?? null)">
          <UploadCloud :size="24" :stroke-width="1.5" style="color: var(--accent-primary);" />
          <div class="text-sm font-medium" style="color: var(--text-primary);">.onnx 파일을 놓거나 클릭해서 선택</div>
          <input ref="fileInput" type="file" accept=".onnx" class="hidden" @change="pickOnnx(($event.target as HTMLInputElement).files); ($event.target as HTMLInputElement).value = ''" />
        </div>
        <div v-if="localFile" class="mt-2 flex items-center gap-2 text-xs"><Badge tone="code">{{ localFile.name }}</Badge><span style="color: var(--text-muted);">{{ (localFile.size / 1024 / 1024).toFixed(1) }}MB</span><button class="text-xs" style="color: var(--text-muted);" @click="localFile = null">제거</button></div>
        <label class="block mt-3 text-xs" style="color: var(--text-secondary);">모델명 (DB 등록용) <input v-model="localName" placeholder="비우면 파일명에서 자동 생성 — 영문·숫자·_" class="mt-1 w-full rounded-md px-2.5 py-1.5 text-sm font-mono" style="background: var(--bg-elevated); border: 1px solid var(--border-strong); color: var(--text-primary);" /></label>
        <div class="mt-3"><Button :busy="v.onnxBusy === 'upload'" :disabled="!localFile" @click="v.uploadLocal(localFile!, localName)">{{ v.onnxBusy === 'upload' ? 'DB 에 적재 중…' : '로컬 파일 DB 적재' }}</Button></div>
        <div v-if="v.onnxLocalResult" class="mt-3 px-3 py-2 rounded-md text-xs" :style="{ background: v.onnxLocalResult.success ? 'var(--accent-positive-soft)' : 'var(--accent-negative-soft)', borderLeft: `3px solid ${v.onnxLocalResult.success ? 'var(--accent-positive)' : 'var(--accent-negative)'}`, color: 'var(--text-primary)' }">
          {{ v.onnxLocalResult.success ? `${v.onnxLocalResult.message} (${v.onnxLocalResult.size_mb}MB · ${fmtNum(v.onnxLocalResult.elapsed_ms ?? 0)}ms)` : v.onnxLocalResult.error }}
        </div>
      </Card>
      <Card title="OCI Object Storage 에서 적재" subtitle="DBMS_CLOUD.GET_OBJECT → DATA_PUMP_DIR → LOAD_ONNX_MODEL" :icon="Cloud">
        <label class="block text-xs" style="color: var(--text-secondary);">Location URI (PAR URL, 끝에 /o/ 까지) <input v-model="cloudUri" placeholder="https://objectstorage.…/p/…/n/…/b/…/o/" class="mt-1 w-full rounded-md px-2.5 py-1.5 text-sm font-mono" style="background: var(--bg-elevated); border: 1px solid var(--border-strong); color: var(--text-primary);" /></label>
        <label class="block mt-2 text-xs" style="color: var(--text-secondary);">ONNX 파일명 <input v-model="cloudFile" placeholder="예: multilingual_e5_small.onnx" class="mt-1 w-full rounded-md px-2.5 py-1.5 text-sm font-mono" style="background: var(--bg-elevated); border: 1px solid var(--border-strong); color: var(--text-primary);" /></label>
        <label class="block mt-2 text-xs" style="color: var(--text-secondary);">모델명 (선택) <input v-model="cloudName" placeholder="비우면 파일명에서 자동 생성" class="mt-1 w-full rounded-md px-2.5 py-1.5 text-sm font-mono" style="background: var(--bg-elevated); border: 1px solid var(--border-strong); color: var(--text-primary);" /></label>
        <div class="mt-3"><Button :busy="v.onnxBusy === 'cloud'" :disabled="!cloudUri.trim() || !cloudFile.trim()" @click="v.loadCloud(cloudUri, cloudFile, cloudName)">{{ v.onnxBusy === 'cloud' ? 'DB 에 적재 중…' : 'Object Storage 에서 DB 적재' }}</Button></div>
        <div v-if="v.onnxCloudResult" class="mt-3 px-3 py-2 rounded-md text-xs" :style="{ background: v.onnxCloudResult.success ? 'var(--accent-positive-soft)' : 'var(--accent-negative-soft)', borderLeft: `3px solid ${v.onnxCloudResult.success ? 'var(--accent-positive)' : 'var(--accent-negative)'}`, color: 'var(--text-primary)' }">
          {{ v.onnxCloudResult.success ? `${v.onnxCloudResult.message} (${fmtNum(v.onnxCloudResult.elapsed_ms ?? 0)}ms)` : v.onnxCloudResult.error }}
        </div>
      </Card>
    </div>

    <Card title="실행 PL/SQL 참고" subtitle="적재 버튼이 서버에서 돌리는 것과 같은 절차">
      <SqlBlock :code="ONNX_LOAD_PLSQL" label="PL/SQL" line-numbers max-height="420px" />
    </Card>

    <ConfirmModal :open="!!pendingSource" title="임베딩 소스를 바꿀까요?" confirm-label="변경" :busy="switching" @confirm="confirmSource" @cancel="pendingSource = null">
      임베딩 소스를 바꾸면 벡터 차원이 달라질 수 있습니다. 기존 문서의 임베딩과 호환되지 않으므로 Vector Store 를 초기화하고 문서를 다시 올려야 합니다. 지금 검색 스레드는 세션 탭으로 보관됩니다.
    </ConfirmModal>
    <ConfirmModal :open="askReset" title="Vector Store 를 초기화할까요?" danger confirm-label="초기화" :busy="v.tableBusy !== ''" @confirm="askReset = false; v.resetStore()" @cancel="askReset = false">
      취소하면 데이터는 남지만, 차원이 다르면 업로드·검색에서 ORA-51932 가 납니다.
    </ConfirmModal>
    <ConfirmModal :open="!!pendingDelete" :title="`모델 ${pendingDelete ?? ''} 을(를) DB 에서 삭제할까요?`" danger confirm-label="삭제" :busy="v.onnxBusy === 'delete'" @confirm="v.deleteModel(pendingDelete!); pendingDelete = null" @cancel="pendingDelete = null">
      삭제 후 이 모델로 만든 임베딩은 더 이상 쓸 수 없습니다.
    </ConfirmModal>
  </div>
</template>

<style scoped>
.drop { border: 2px dashed var(--border-strong); background: var(--bg-surface); }
.drop:hover, .drop.over { border-color: var(--accent-primary); background: var(--accent-primary-soft); }
.row + .row { border-top: 1px solid var(--border-default); }
</style>
