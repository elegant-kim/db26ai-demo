<script setup lang="ts">
/**
 * 「환경」 서브탭 — 시연의 시작점. Select AI 가 왜 동작하는가를 한 화면에 놓는다 (2026-09-07 재설계).
 * ① 프로필이 무엇을 보는가 → ② 프로필의 credential_name 이 가리키는 크리덴셜 → ③ provider_endpoint 의 호스트에 대한 ACL.
 * 11건을 덤프하지 않고 이 프로필에 해당하는 것만 보여준다. 조회 SQL 은 접어 두고 펼친다.
 * 마지막 「실제 호출 테스트」가 세 카드가 전부 ✓ 여도 키가 만료됐으면 실패한다는 것을 그 자리에서 드러낸다.
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Bot, KeyRound, Network, PlugZap, RefreshCw, ChevronRight, ChevronDown, MessageSquareText } from 'lucide-vue-next'
import Card from '@/components/ui/Card.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import LoadingBlock from '@/components/ui/LoadingBlock.vue'
import EmptyState from '@/components/demo/EmptyState.vue'
import KvGrid from '@/components/demo/KvGrid.vue'
import SqlBlock from '@/components/demo/SqlBlock.vue'
import ResultTable from '@/components/demo/ResultTable.vue'
import VersusBox from '@/components/demo/VersusBox.vue'
import { fmtMs } from '@/lib/format'
import type { Rows } from '@/lib/normalize'
import { ENV_TEST_PROMPT } from '@/lib/nl2sql'
import { useNl2sqlStore } from '@/stores/nl2sql'

const s = useNl2sqlStore()
const route = useRoute()
// `?profile=…&run=1` — run 은 실제 호출 테스트를 바로 돌린다 (설계서 05 §3.3 의 run 규약)
onMounted(() => { void s.init(route.query.profile).then(async () => { await s.loadEnv(); if (route.query.run !== undefined) void s.testCall() }) })

const showSql = ref<Record<string, boolean>>({})
const showAllAcl = ref(false)
const toggleSql = (k: string) => { showSql.value[k] = !showSql.value[k] }

// 속성 표 3열을 그대로 보여주지 않는다 — 키:값으로 읽히게, 불리언은 ✓/✗, object_list 는 아래 칩으로
const bool = (v: string | undefined) => (v === 'true' ? '✓ 켜짐' : v === 'false' ? '✗ 꺼짐' : v || '—')
const profileKv = computed(() => {
  const a = s.profileAttrs
  return {
    provider: a.provider || '—',
    model: a.model || '—',
    provider_endpoint: a.provider_endpoint || '—',
    credential_name: a.credential_name || '—',
    annotations: bool(a.annotations),
    comments: bool(a.comments),
    constraints: bool(a.constraints),
    conversation: bool(a.conversation),
  }
})
const credKv = computed(() => {
  const r = s.credentialRow
  return r ? { credential_name: String(r.CREDENTIAL_NAME ?? '—'), username: String(r.USERNAME ?? '—'), enabled: String(r.ENABLED ?? '—') } : null
})
const PRIVS = ['CONNECT', 'RESOLVE', 'HTTP']
const aclHostRows = computed<Rows>(() => ({
  columns: ['PRINCIPAL', 'PRIVILEGE', 'GRANT_TYPE'],
  rows: s.aclForHost.map((r) => ({ PRINCIPAL: r.PRINCIPAL ?? '—', PRIVILEGE: r.PRIVILEGE ?? '—', GRANT_TYPE: r.GRANT_TYPE ?? r.STATUS ?? '—' })),
}))
</script>

<template>
  <div class="w-full flex flex-col gap-4">
    <!-- 시연 전에 볼 것: Select AI 가 무엇인가 (질문 탭에서 옮겨 왔다 — 시연 중이 아니라 시연 전의 내용이라서) -->
    <Card title="Oracle Select AI — 자연어로 데이터를 질의하다" :icon="MessageSquareText" compact>
      <VersusBox left-title="기존 방식" left-desc="개발자가 SQL 을 직접 작성. 스키마 이해 필수. 앱마다 쿼리 개발."
        right-title="Oracle Select AI" right-desc="자연어 → DB 가 SQL 을 자동 생성. AI 프로필이 스키마를 참조. 프로필 하나로 다양한 질문에 대응.">
        SQL 을 몰라도 데이터를 물을 수 있습니다. <strong style="color: var(--text-primary);">DB 안에서</strong> <code class="font-mono">DBMS_CLOUD_AI.GENERATE</code> 한 줄로 동작합니다.
        그러려면 아래 세 가지가 맞아 있어야 합니다 — <strong style="color: var(--text-primary);">프로필</strong>이 무엇을 보는지, <strong style="color: var(--text-primary);">크리덴셜</strong>에 LLM 키가 있는지, <strong style="color: var(--text-primary);">네트워크 ACL</strong>이 DB 를 밖으로 내보내는지.
      </VersusBox>
    </Card>

    <div v-if="s.lastError" class="px-3 py-2.5 rounded-md text-sm" style="background: var(--accent-negative-soft); border-left: 3px solid var(--accent-negative); color: var(--text-primary);">{{ s.lastError }}</div>

    <LoadingBlock v-if="s.envLoading && !s.env.profile" label="환경을 읽는 중…" hint="프로필 속성 · 크리덴셜 · 네트워크 ACL 을 함께 조회합니다" />
    <EmptyState v-else-if="!s.profile" :icon="Bot" title="AI 프로필이 없습니다" desc="DBMS_CLOUD_AI.CREATE_PROFILE 로 프로필을 만들면 여기에 나타납니다 (sql/setup/51_selectai_adb_setup.sql §4)." />

    <template v-else>
      <!-- 상태 스트립: 한 줄 요약. 아래 세 카드의 결론만 모아 놓는다 -->
      <Card compact>
        <div class="flex flex-wrap items-center gap-2">
          <Badge tone="primary">프로필 · {{ s.profile }}</Badge>
          <Badge tone="code">{{ s.profileAttrs.model || '—' }}</Badge>
          <Badge :tone="s.credOk ? 'positive' : 'negative'">크리덴셜 {{ s.credOk ? '✓' : '✗' }} {{ s.credentialName || '—' }}</Badge>
          <Badge :tone="s.aclOk ? 'positive' : 'negative'">ACL {{ s.aclOk ? '✓' : '✗' }} {{ s.endpointHost || '—' }}</Badge>
          <Badge tone="info">참조 테이블 {{ s.objectList.length }}</Badge>
          <Badge tone="info">Annotation {{ s.annotationCount }}</Badge>
          <span class="ml-auto"><Button size="sm" variant="ghost" :busy="s.envLoading" @click="s.loadEnv(true)"><RefreshCw :size="14" :stroke-width="1.75" /> 새로고침</Button></span>
        </div>
      </Card>

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-4 items-start">
        <!-- ① 프로필 -->
        <Card title="① AI 프로필" subtitle="어느 LLM 으로 어느 테이블을 보는가" :icon="Bot">
          <KvGrid :data="profileKv" :cols="1" />
          <div class="mt-3">
            <div class="text-xs mb-1.5" style="color: var(--text-muted);">object_list · 참조 테이블 {{ s.objectList.length }}개</div>
            <div v-if="s.objectList.length" class="flex flex-wrap gap-1">
              <Badge v-for="t in s.objectList" :key="t.owner + '.' + t.name" tone="code">{{ t.owner }}.{{ t.name }}</Badge>
            </div>
            <div v-else class="text-sm" style="color: var(--accent-negative);">비어 있습니다 — LLM 이 볼 테이블이 없습니다.</div>
          </div>
          <button type="button" class="mt-3 inline-flex items-center gap-1 text-xs" style="color: var(--text-muted);" @click="toggleSql('profile')">
            <component :is="showSql.profile ? ChevronDown : ChevronRight" :size="12" :stroke-width="2" /> 조회 SQL
          </button>
          <SqlBlock v-if="showSql.profile" class="mt-2" :code="s.env.profile?.sql_executed" label="DBA_CLOUD_AI_PROFILE_ATTRIBUTES" max-height="160px" />
        </Card>

        <!-- ② 크리덴셜 -->
        <Card title="② LLM 크리덴셜" subtitle="← 프로필의 credential_name" :icon="KeyRound">
          <template v-if="credKv">
            <KvGrid :data="credKv" :cols="1" />
            <p class="text-[11px] mt-3 m-0" style="color: var(--text-muted); line-height: 1.5;">
              <strong style="color: var(--accent-warm);">ENABLED='TRUE' 는 키가 등록됐다는 뜻이지 유효하다는 뜻이 아닙니다.</strong>
              만료된 키도 TRUE 로 보입니다. 유효성은 아래 「실제 호출 테스트」로만 압니다. API 키 값은 어떤 뷰에도 나오지 않습니다.
            </p>
          </template>
          <div v-else class="text-sm" style="color: var(--accent-negative);">
            프로필이 가리키는 크리덴셜 <span class="font-mono">{{ s.credentialName || '—' }}</span> 이 없습니다 → 호출 시 실패합니다.
            <div class="text-[11px] mt-1" style="color: var(--text-muted);">DBMS_CLOUD.CREATE_CREDENTIAL 로 만듭니다 (51번 §3).</div>
          </div>
          <button type="button" class="mt-3 inline-flex items-center gap-1 text-xs" style="color: var(--text-muted);" @click="toggleSql('credential')">
            <component :is="showSql.credential ? ChevronDown : ChevronRight" :size="12" :stroke-width="2" /> 조회 SQL
          </button>
          <SqlBlock v-if="showSql.credential" class="mt-2" :code="s.env.credential?.sql_executed" label="USER_CREDENTIALS" max-height="160px" />
        </Card>

        <!-- ③ ACL -->
        <Card title="③ 네트워크 ACL" subtitle="← 프로필의 provider_endpoint 호스트" :icon="Network">
          <div v-if="!s.endpointHost" class="text-sm" style="color: var(--text-muted);">프로필에 provider_endpoint 가 없어 확인할 호스트가 없습니다.</div>
          <template v-else>
            <div class="font-mono text-sm break-all mb-2" style="color: var(--text-primary);">{{ s.endpointHost }}</div>
            <div class="flex flex-wrap gap-1.5 mb-3">
              <Badge v-for="p in PRIVS" :key="p" :tone="s.aclPrivs.has(p) ? 'positive' : 'default'">{{ p }} {{ s.aclPrivs.has(p) ? '✓' : '—' }}</Badge>
            </div>
            <ResultTable v-if="s.aclForHost.length" :rows="aclHostRows" dense hide-footer max-height="200px" />
            <div v-else class="text-sm" style="color: var(--accent-negative);">이 호스트에 부여된 ACE 가 없습니다 → 호출 시 <span class="font-mono">ORA-24247</span></div>
          </template>
          <p class="text-[11px] mt-3 m-0" style="color: var(--text-muted); line-height: 1.5;">
            아웃바운드에 필요한 것은 <span class="font-mono">CONNECT</span> · <span class="font-mono">RESOLVE</span> 입니다. <span class="font-mono">HTTP</span> 는 XDB 용이라 없어도 됩니다.
          </p>
          <div class="mt-3 flex items-center gap-3">
            <button type="button" class="inline-flex items-center gap-1 text-xs" style="color: var(--text-muted);" @click="toggleSql('acl')">
              <component :is="showSql.acl ? ChevronDown : ChevronRight" :size="12" :stroke-width="2" /> 조회 SQL
            </button>
            <button v-if="s.aclAll" type="button" class="inline-flex items-center gap-1 text-xs" style="color: var(--text-muted);" @click="showAllAcl = !showAllAcl">
              <component :is="showAllAcl ? ChevronDown : ChevronRight" :size="12" :stroke-width="2" /> 전체 {{ s.aclAll.rows.length }}건
            </button>
          </div>
          <SqlBlock v-if="showSql.acl" class="mt-2" :code="s.env.acl?.sql_executed" label="DBA_HOST_ACES" max-height="160px" />
          <ResultTable v-if="showAllAcl && s.aclAll" class="mt-2" :rows="s.aclAll" dense hide-footer max-height="260px" />
        </Card>
      </div>

      <!-- 실제 호출 테스트 — 51번 SQL §6-6 을 화면으로 -->
      <Card title="실제 호출 테스트" :subtitle="`chat 액션으로 '${ENV_TEST_PROMPT}' 를 보냅니다 — 테이블을 읽지 않으므로 크리덴셜 · ACL · LLM 경로만 탑니다`" :icon="PlugZap">
        <template #actions>
          <Button size="sm" :busy="s.envTest.busy" :disabled="!s.profile" @click="s.testCall()"><PlugZap :size="14" :stroke-width="1.75" /> {{ s.profile }} 로 호출</Button>
        </template>
        <LoadingBlock v-if="s.envTest.busy" compact label="LLM 을 호출하는 중…" hint="첫 호출은 TLS · 모델 로딩 때문에 수 초 걸립니다" />
        <div v-else-if="s.envTest.error" class="px-3 py-2.5 rounded-md text-sm" style="background: var(--accent-negative-soft); border-left: 3px solid var(--accent-negative); color: var(--text-primary);">
          <strong>실패:</strong> <span class="font-mono text-xs break-all">{{ s.envTest.error }}</span>
          <div class="text-[11px] mt-1.5" style="color: var(--text-muted);">
            <span class="font-mono">ORA-20404</span> → 크리덴셜의 API 키 · <span class="font-mono">ORA-24247</span> → 네트워크 ACL · <span class="font-mono">ORA-20046</span> → 세션 프로필(앱은 매 호출 프로필명을 명시하므로 나올 일이 없습니다)
          </div>
        </div>
        <div v-else-if="s.envTest.response" class="flex items-start gap-3">
          <div class="flex-1 text-sm whitespace-pre-wrap" style="color: var(--text-primary);">{{ s.envTest.response }}</div>
          <Badge v-if="s.envTest.elapsedMs != null" tone="code">{{ fmtMs(s.envTest.elapsedMs) }}</Badge>
        </div>
        <div v-else class="text-sm" style="color: var(--text-muted);">세 카드가 전부 ✓ 여도 키가 만료됐으면 실패합니다. 시연 전에 한 번 눌러 둡니다.</div>
      </Card>
    </template>
  </div>
</template>
