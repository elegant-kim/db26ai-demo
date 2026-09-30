<script setup lang="ts">
/**
 * 「새 프로필 만들기」 모달 (PoC 3-A) — provider · 모델 · 크리덴셜 · object_list · 플래그를 받아 DBMS_CLOUD_AI.CREATE_PROFILE PL/SQL 을 미리보고 실행.
 * OCI Generative AI 는 region 필수(한국 리전엔 GenAI 없음 → 오사카 등 제공 리전만 선택지), 전용 클러스터면 oci_endpoint_id.
 */
import { computed, ref, watch } from 'vue'
import { X as XIcon, Eye, Play, Info } from 'lucide-vue-next'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import SqlBlock from '@/components/demo/SqlBlock.vue'
import LoadingBlock from '@/components/ui/LoadingBlock.vue'
import { errorMessage } from '@/lib/api'
import { createProfile, getWizardMeta, type ProfileForm, type WizardMeta } from '@/lib/nl2sql'
import { useSystemStore } from '@/stores/system'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: []; created: [string] }>()
const system = useSystemStore()
const meta = ref<WizardMeta | null>(null)
const loading = ref(false)
const name = ref('')
const desc = ref('')
const form = ref<ProfileForm>({ provider: 'openai', credential_name: '', model: '', provider_endpoint: '', region: 'ap-osaka-1', oci_compartment_id: '', oci_apiformat: 'GENERIC', oci_endpoint_id: '', azure_resource_name: '', azure_deployment_name: '', object_list: [], annotations: true, comments: true, constraints: true, conversation: true, embedding_model: '' })
const plsql = ref('')
const errors = ref<string[]>([])
const busy = ref(false)
const tableFilter = ref('')

watch(() => props.open, async (o) => { if (o && !meta.value) { loading.value = true; try { meta.value = await getWizardMeta() } catch (e) { system.toast(errorMessage(e), 'error') } finally { loading.value = false } } })
const prov = computed(() => meta.value?.providers.find((p) => p.id === form.value.provider))
const isOci = computed(() => form.value.provider === 'oci')
const isAzure = computed(() => form.value.provider === 'azure')
const tables = computed(() => (meta.value?.tables ?? []).filter((t) => !tableFilter.value || t.name.toLowerCase().includes(tableFilter.value.toLowerCase())))
const picked = (t: { owner: string; name: string }) => form.value.object_list.some((o) => o.owner === t.owner && o.name === t.name)
function toggleTable(t: { owner: string; name: string }) { const i = form.value.object_list.findIndex((o) => o.owner === t.owner && o.name === t.name); if (i >= 0) form.value.object_list.splice(i, 1); else form.value.object_list.push({ owner: t.owner, name: t.name }) }
function usePreset(url: string) { form.value.provider_endpoint = url }
async function preview() {
  busy.value = true; errors.value = []
  try { const r = await createProfile(name.value, form.value, desc.value, true); plsql.value = r.plsql ?? ''; if (!r.success) errors.value = r.errors ?? [r.error ?? '검증 실패'] }
  catch (e: any) { const d = e?.response?.data; plsql.value = d?.plsql ?? ''; errors.value = d?.errors ?? [errorMessage(e)] } finally { busy.value = false }
}
async function run() {
  busy.value = true; errors.value = []
  try {
    const r = await createProfile(name.value, form.value, desc.value, false)
    plsql.value = r.plsql ?? plsql.value
    if (!r.success) { errors.value = r.errors ?? [r.error ?? '생성 실패']; return }
    system.toast(`프로필 ${r.profile_name} 을 만들었습니다`, 'success'); emit('created', r.profile_name!)
  } catch (e: any) { const d = e?.response?.data; plsql.value = d?.plsql ?? plsql.value; errors.value = d?.errors ?? [errorMessage(e)] } finally { busy.value = false }
}
const inputStyle = 'background: var(--bg-elevated); border: 1px solid var(--border-strong); color: var(--text-primary);'
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="fixed inset-0 z-[60] flex items-center justify-center p-4" style="background: rgba(0,0,0,0.5);" @click.self="emit('close')">
      <div class="w-full max-w-[960px] max-h-[92vh] flex flex-col rounded-md" style="background: var(--bg-elevated); box-shadow: var(--shadow-elevated);" role="dialog" aria-label="새 프로필 만들기">
        <header class="flex items-center justify-between px-5 py-3 shrink-0" style="border-bottom: 1px solid var(--border-default);">
          <div><div class="font-semibold" style="color: var(--text-primary);">새 프로필 만들기</div><div class="text-[11px]" style="color: var(--text-muted);">DBMS_CLOUD_AI.CREATE_PROFILE — 폼 → PL/SQL 미리보기 → 실행. 크리덴셜은 미리 DBMS_CLOUD.CREATE_CREDENTIAL 로 만들어 둔다(키는 여기 안 적는다)</div></div>
          <button class="p-1.5 rounded-md" style="color: var(--text-secondary);" @click="emit('close')"><XIcon :size="18" :stroke-width="1.75" /></button>
        </header>
        <div class="flex-1 overflow-auto p-5">
          <LoadingBlock v-if="loading || !meta" compact label="선택지를 읽는 중…" />
          <div v-else class="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <!-- 왼쪽: 폼 -->
            <div class="flex flex-col gap-3 text-sm">
              <label class="flex flex-col gap-1"><span class="text-xs" style="color: var(--text-muted);">프로필 이름</span><input v-model="name" placeholder="예: OCI_OSAKA_PROFILE" class="rounded-md px-2.5 py-1.5 font-mono" :style="inputStyle" /></label>
              <label class="flex flex-col gap-1"><span class="text-xs" style="color: var(--text-muted);">provider</span>
                <select v-model="form.provider" class="rounded-md px-2.5 py-1.5" :style="inputStyle"><option v-for="p in meta.providers" :key="p.id" :value="p.id">{{ p.id }} — {{ p.label }}</option></select>
                <span v-if="prov?.hint" class="text-[11px]" style="color: var(--text-muted);">{{ prov.hint }}</span>
              </label>
              <label class="flex flex-col gap-1"><span class="text-xs" style="color: var(--text-muted);">credential_name</span>
                <select v-model="form.credential_name" class="rounded-md px-2.5 py-1.5" :style="inputStyle"><option value="">— 고르기 —</option><option v-for="c in meta.credentials" :key="c.credential_name" :value="c.credential_name">{{ c.credential_name }} ({{ c.kind === 'oci_api_key' ? 'OCI API Key' : c.kind === 'resource_principal' ? 'Resource Principal' : 'API 키' }}{{ c.enabled === 'TRUE' ? '' : ' · 비활성' }})</option></select>
              </label>
              <label class="flex flex-col gap-1"><span class="text-xs" style="color: var(--text-muted);">model</span>
                <input v-model="form.model" list="wiz-models" :placeholder="isOci ? 'cohere.command-r-plus-08-2024 …' : 'gemini-3.8-flash · gpt-4o …'" class="rounded-md px-2.5 py-1.5 font-mono" :style="inputStyle" />
                <datalist id="wiz-models"><option v-for="m in (isOci ? meta.oci_models : [])" :key="m" :value="m" /></datalist>
              </label>
              <template v-if="prov?.endpoint">
                <label class="flex flex-col gap-1"><span class="text-xs" style="color: var(--text-muted);">provider_endpoint</span><input v-model="form.provider_endpoint" placeholder="https://…" class="rounded-md px-2.5 py-1.5 font-mono text-xs" :style="inputStyle" />
                  <span class="flex flex-wrap gap-1 mt-0.5"><button v-for="e in meta.endpoint_presets" :key="e.url" type="button" class="text-[11px] px-1.5 py-0.5 rounded" style="background: var(--bg-surface); color: var(--text-secondary);" @click="usePreset(e.url)">{{ e.label }}</button></span>
                </label>
              </template>
              <template v-if="isOci">
                <label class="flex flex-col gap-1"><span class="text-xs" style="color: var(--text-muted);">region <b style="color: var(--accent-negative);">필수</b></span>
                  <select v-model="form.region" class="rounded-md px-2.5 py-1.5" :style="inputStyle"><option v-for="r in meta.oci_regions" :key="r.id" :value="r.id">{{ r.label }}</option></select>
                  <span class="text-[11px] flex items-start gap-1" style="color: var(--text-muted);"><Info :size="12" :stroke-width="1.75" class="shrink-0 mt-0.5" /> 한국 리전(서울·춘천)에는 Generative AI 가 없어 목록에 없다. ADB 가 있는 테넌시에서 해당 리전을 구독해야 한다.</span>
                </label>
                <div class="grid grid-cols-2 gap-2">
                  <label class="flex flex-col gap-1"><span class="text-xs" style="color: var(--text-muted);">oci_apiformat</span><select v-model="form.oci_apiformat" class="rounded-md px-2.5 py-1.5" :style="inputStyle"><option>GENERIC</option><option>COHERE</option></select></label>
                  <label class="flex flex-col gap-1"><span class="text-xs" style="color: var(--text-muted);">oci_compartment_id (선택)</span><input v-model="form.oci_compartment_id" placeholder="ocid1.compartment.oc1…" class="rounded-md px-2.5 py-1.5 font-mono text-xs" :style="inputStyle" /></label>
                </div>
                <label class="flex flex-col gap-1"><span class="text-xs" style="color: var(--text-muted);">oci_endpoint_id (전용 클러스터일 때)</span><input v-model="form.oci_endpoint_id" placeholder="ocid1.generativeaiendpoint…" class="rounded-md px-2.5 py-1.5 font-mono text-xs" :style="inputStyle" /></label>
              </template>
              <template v-if="isAzure">
                <div class="grid grid-cols-2 gap-2">
                  <label class="flex flex-col gap-1"><span class="text-xs" style="color: var(--text-muted);">azure_resource_name</span><input v-model="form.azure_resource_name" class="rounded-md px-2.5 py-1.5 font-mono text-xs" :style="inputStyle" /></label>
                  <label class="flex flex-col gap-1"><span class="text-xs" style="color: var(--text-muted);">azure_deployment_name</span><input v-model="form.azure_deployment_name" class="rounded-md px-2.5 py-1.5 font-mono text-xs" :style="inputStyle" /></label>
                </div>
              </template>
              <div class="flex flex-col gap-1">
                <span class="text-xs flex items-center gap-2" style="color: var(--text-muted);">object_list — LLM 이 볼 테이블 <Badge>{{ form.object_list.length }}</Badge><input v-model="tableFilter" placeholder="필터" class="ml-auto rounded px-2 py-0.5 text-xs w-32" :style="inputStyle" /></span>
                <div class="rounded-md overflow-auto max-h-[180px] p-1 flex flex-col" style="border: 1px solid var(--border-default);">
                  <label v-for="t in tables" :key="t.owner + t.name" class="flex items-center gap-2 text-xs px-1.5 py-0.5 rounded cursor-pointer" style="color: var(--text-primary);"><input type="checkbox" :checked="picked(t)" @change="toggleTable(t)" /><span class="font-mono">{{ t.name }}</span><span class="truncate" style="color: var(--text-muted);">{{ t.comment || '' }}</span><span class="ml-auto tabular-nums" style="color: var(--text-muted);">{{ t.num_rows ?? '' }}</span></label>
                </div>
              </div>
              <div class="flex flex-wrap gap-x-4 gap-y-1 text-xs" style="color: var(--text-secondary);">
                <label class="flex items-center gap-1"><input v-model="form.annotations" type="checkbox" /> annotations</label>
                <label class="flex items-center gap-1"><input v-model="form.comments" type="checkbox" /> comments</label>
                <label class="flex items-center gap-1"><input v-model="form.constraints" type="checkbox" /> constraints</label>
                <label class="flex items-center gap-1"><input v-model="form.conversation" type="checkbox" /> conversation</label>
              </div>
              <label class="flex flex-col gap-1"><span class="text-xs" style="color: var(--text-muted);">embedding_model (피드백을 쓰려면 — OpenAI 호환은 필수, 예: gemini-embedding-001)</span><input v-model="form.embedding_model" class="rounded-md px-2.5 py-1.5 font-mono text-xs" :style="inputStyle" /></label>
              <label class="flex flex-col gap-1"><span class="text-xs" style="color: var(--text-muted);">description (선택)</span><input v-model="desc" class="rounded-md px-2.5 py-1.5" :style="inputStyle" /></label>
            </div>
            <!-- 오른쪽: 미리보기 -->
            <div class="flex flex-col gap-3">
              <div class="flex items-center gap-2"><Button size="sm" variant="secondary" :busy="busy" @click="preview"><Eye :size="14" :stroke-width="1.75" /> PL/SQL 미리보기</Button><Button size="sm" :busy="busy" :disabled="!name.trim()" @click="run"><Play :size="14" :stroke-width="1.75" /> 실행 (CREATE_PROFILE)</Button></div>
              <div v-if="errors.length" class="text-xs px-3 py-2 rounded-md flex flex-col gap-0.5" style="background: var(--accent-negative-soft); color: var(--text-primary);"><div v-for="e in errors" :key="e" class="font-mono break-all">{{ e }}</div></div>
              <SqlBlock v-if="plsql" :code="plsql" label="DBMS_CLOUD_AI.CREATE_PROFILE" max-height="520px" />
              <p v-else class="text-xs m-0" style="color: var(--text-muted);">폼을 채우고 「미리보기」를 누르면 실행될 PL/SQL 이 여기 보입니다. 실행 후 환경 탭이 새 프로필로 바뀌고, 「실제 호출 테스트」로 프로바이더에 관계없이 경로를 확인합니다.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
