<template>
  <section class="page" data-module="certification">
    <header class="page-head">
      <div>
        <h2>认证认可管理</h2>
        <p class="page-desc">维护资质认定，按认定编号查看认定范围、发证机构与有效期；资质覆盖视图展示每份认定可开展的检测项目。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记资质认定</button>
        <button class="btn" type="button" @click="exportRows">导出资质清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <div class="view-switch" role="tablist">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        role="tab"
        :class="['switch-btn', { active: view === tab.key }]"
        @click="view = tab.key"
      >
        {{ tab.label }}
      </button>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>认定编号 / 发证机构 / 认定范围</span>
        <input v-model="filters.keyword" placeholder="按关键字检索" />
      </label>
      <label class="filter-item">
        <span>认定类型</span>
        <select v-model="filters.certType" @change="reload">
          <option value="">全部类型</option>
          <option v-for="item in certTypes" :key="item['认定类型']" :value="item['认定类型']">
            {{ item['认定类型'] }}
          </option>
        </select>
      </label>
      <label class="filter-item">
        <span>认定状态</span>
        <select v-model="filters.status" @change="reload">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <!-- 资质覆盖视图：已过期、临期固定排在最前面，同组按有效期至升序 -->
    <template v-if="view === 'coverage'">
      <section v-for="group in statusGroups" :key="group.status" class="coverage-group">
        <header v-if="group.rows.length" class="group-head">
          <span :class="['status-tag', `tag-${group.status}`]">{{ group.status }}</span>
          <span class="group-count">{{ group.rows.length }} 份</span>
        </header>
        <table v-if="group.rows.length" class="data-table">
          <thead>
            <tr>
              <th>认定编号</th>
              <th>认定类型</th>
              <th>认定范围（点击查看检测项目）</th>
              <th>发证机构</th>
              <th>获证日期</th>
              <th>有效期至</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in group.rows" :key="String(row.id)">
              <td>{{ row['认定编号'] ?? '—' }}</td>
              <td>{{ row['认定类型'] ?? '—' }}</td>
              <td>
                <div class="scope-links">
                  <button
                    v-for="scope in row.scopes"
                    :key="scope['认定范围']"
                    type="button"
                    class="link scope-link"
                    @click="openScope(row, scope['认定范围'])"
                  >
                    {{ scope['认定范围'] }}
                    <span class="scope-count">可开展 {{ scope['可开展项目数'] }} 项</span>
                  </button>
                </div>
              </td>
              <td>{{ row['发证机构'] ?? '—' }}</td>
              <td>{{ row['获证日期'] ?? '—' }}</td>
              <td>{{ row['有效期至'] ?? '—' }}</td>
            </tr>
          </tbody>
        </table>
      </section>
      <p v-if="!coverageRows.length" class="empty-state block-empty">当前筛选条件下暂无资质认定记录</p>
    </template>

    <!-- 资质台账视图：与覆盖视图同口径、同排列顺序 -->
    <table v-else class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in ledgerRows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">
            <span v-if="column === '认定状态'" :class="['status-tag', `tag-${String(row[column])}`]">
              {{ row[column] ?? '—' }}
            </span>
            <span v-else>{{ row[column] ?? '—' }}</span>
          </td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!ledgerRows.length">
          <td :colspan="columns.length + 1" class="empty-state">当前筛选条件下暂无资质认定记录</td>
        </tr>
      </tbody>
    </table>

    <!-- 认定范围下钻：该范围内可开展的检测项目清单，未覆盖项给出暂无覆盖说明 -->
    <div v-if="scopeOpen" class="modal-mask" role="dialog" aria-modal="true" @click.self="closeScope">
      <div class="modal-panel">
        <header class="modal-head">
          <div>
            <h3>{{ scopeDetail ? `${scopeDetail['认定范围']} · 检测项目覆盖清单` : '检测项目覆盖清单' }}</h3>
            <p v-if="scopeDetail" class="modal-sub">
              {{ scopeDetail['认定编号'] }}（{{ scopeDetail['认定类型'] }}） · {{ scopeDetail['发证机构'] }}
              ｜获证 {{ scopeDetail['获证日期'] }} ｜有效期至 {{ scopeDetail['有效期至'] }}
            </p>
          </div>
          <button type="button" class="btn ghost" @click="closeScope">关闭</button>
        </header>
        <p v-if="scopeError" class="error-text">{{ scopeError }}</p>
        <template v-else-if="scopeDetail">
          <p class="scope-summary">
            该范围目录共 {{ scopeDetail.items.length }} 个检测项目：
            <strong class="covered-text">可开展 {{ scopeDetail.covered_count }} 项</strong>，
            <strong class="uncovered-text">暂无覆盖 {{ scopeDetail.uncovered_count }} 项</strong>
          </p>
          <table class="data-table">
            <thead>
              <tr>
                <th>检测项目</th>
                <th>检测标准</th>
                <th>覆盖状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in scopeDetail.items" :key="String(item['检测项目'])" :class="{ 'row-uncovered': item['覆盖状态'] === '暂无覆盖' }">
                <td>{{ item['检测项目'] }}</td>
                <td>{{ item['检测标准'] ?? '—' }}</td>
                <td>
                  <span v-if="item['覆盖状态'] === '暂无覆盖'" class="uncovered-text">暂无覆盖：本资质认定附表未包含该项目，当前不可据此出具检测报告</span>
                  <span v-else class="covered-text">{{ item['覆盖状态'] }}</span>
                </td>
              </tr>
              <tr v-if="!scopeDetail.items.length">
                <td colspan="3" class="empty-state">该认定范围暂未维护检测项目目录，暂无覆盖信息可展示</td>
              </tr>
            </tbody>
          </table>
        </template>
      </div>
    </div>

    <footer class="page-foot">
      <span>共 {{ total }} 条资质认定记录（覆盖视图与资质台账同口径）</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type TableValue = string | number | null
type LedgerRow = Record<string, TableValue> & {
  id: number
  status: string
  scopes?: ScopeBrief[]
}
type ScopeBrief = { 认定范围: string; 可开展项目数: number }
type ScopeItem = { 检测项目: string; 检测标准: string | null; 覆盖状态: string }
type ScopeDetail = {
  id: number
  认定编号: string
  认定类型: string
  认定状态: string
  发证机构: string
  获证日期: string
  有效期至: string
  认定范围: string
  covered_count: number
  uncovered_count: number
  items: ScopeItem[]
}

const ENDPOINT = '/api/certification'
const columns = ['认定编号', '认定类型', '发证机构', '认定范围', '获证日期', '有效期至', '证书编号', '认定状态']
const actions = ['续证申请', '登记过期', '注销证书']
const statuses = ['已过期', '临期', '有效', '已注销']
const tabs = [
  { key: 'coverage', label: '资质覆盖视图' },
  { key: 'ledger', label: '资质台账视图' },
] as const

const view = ref<(typeof tabs)[number]['key']>('coverage')
const coverageRows = ref<LedgerRow[]>([])
const ledgerRows = ref<LedgerRow[]>([])
const total = ref(0)
const errorMessage = ref('')
const certTypes = ref<Array<Record<string, string>>>([])
const filters = ref({ keyword: '', certType: '', status: '' })

const scopeDetail = ref<ScopeDetail | null>(null)
const scopeOpen = ref(false)
const scopeError = ref('')

const stats = computed(() => {
  const count = (status: string) => coverageRows.value.filter((row) => row.status === status).length
  return [
    { label: '有效资质', value: count('有效') },
    { label: '临期资质', value: count('临期') },
    { label: '已过期资质', value: count('已过期') },
    { label: '已注销资质', value: count('已注销') },
  ]
})

// 覆盖视图按状态分组：已过期、临期在前，有效、已注销在后；组内顺序即后端给出的有效期顺序。
const statusGroups = computed(() =>
  statuses.map((status) => ({
    status,
    rows: coverageRows.value.filter((row) => row.status === status),
  })),
)

function buildQuery(): string {
  const params = new URLSearchParams()
  if (filters.value.keyword.trim()) params.set('keyword', filters.value.keyword.trim())
  if (filters.value.certType) params.set('type', filters.value.certType)
  if (filters.value.status) params.set('status', filters.value.status)
  const query = params.toString()
  return query ? `?${query}` : ''
}

function withSize(query: string, size: number): string {
  const params = new URLSearchParams(query.replace(/^\?/, ''))
  params.set('size', String(size))
  return `?${params.toString()}`
}

function resetFilters() {
  filters.value = { keyword: '', certType: '', status: '' }
  void reload()
}

function exportRows() {
  // 导出走当前筛选条件，后端按当前视图同一排列顺序返回。
  window.open(`${ENDPOINT}/export${buildQuery()}`, '_blank')
}

function openCreate() {
  errorMessage.value = '资质认定登记入口尚未接入审批流'
}

async function runAction(action: string, row: LedgerRow) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('认证认可动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '认证认可操作失败'
  }
}

async function openScope(row: LedgerRow, scope: string) {
  scopeError.value = ''
  scopeDetail.value = null
  scopeOpen.value = true
  try {
    const response = await request(`${ENDPOINT}/coverage/${row.id}?scope=${encodeURIComponent(scope)}`)
    if (response.status === 404) {
      scopeError.value = '该认定范围暂无检测项目目录，请先维护资质附表'
      return
    }
    if (!response.ok) {
      throw new Error('认定范围覆盖清单读取失败')
    }
    scopeDetail.value = (await response.json()) as ScopeDetail
  } catch (error) {
    scopeError.value = error instanceof Error ? error.message : '认定范围覆盖清单读取失败'
  }
}

function closeScope() {
  scopeOpen.value = false
  scopeDetail.value = null
  scopeError.value = ''
}

async function loadTypes() {
  try {
    const response = await request(`${ENDPOINT}/types`)
    if (response.ok) {
      const payload = (await response.json()) as { items?: Array<Record<string, string>> }
      certTypes.value = payload.items ?? []
    }
  } catch {
    // 类型筛选项拉取失败不阻塞主列表
  }
}

async function reload() {
  errorMessage.value = ''
  const query = buildQuery()
  try {
    const [coverageResponse, ledgerResponse] = await Promise.all([
      request(`${ENDPOINT}/coverage${query}`),
      request(`${ENDPOINT}${withSize(query, 200)}`),
    ])
    if (!coverageResponse.ok || !ledgerResponse.ok) {
      throw new Error('资质认定列表读取失败')
    }
    const coveragePayload = (await coverageResponse.json()) as { items?: LedgerRow[]; total?: number }
    const ledgerPayload = (await ledgerResponse.json()) as { items?: LedgerRow[]; total?: number }
    coverageRows.value = coveragePayload.items ?? []
    ledgerRows.value = ledgerPayload.items ?? []
    total.value = ledgerPayload.total ?? ledgerRows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '资质认定列表读取失败'
  }
}

onMounted(() => {
  void loadTypes()
  void reload()
})
</script>

<style scoped>
.view-switch {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.switch-btn {
  border: 1px solid var(--border);
  background: #fff;
  border-radius: 6px;
  padding: 6px 16px;
  cursor: pointer;
  font-size: 13px;
}
.switch-btn.active {
  background: var(--brand);
  border-color: var(--brand);
  color: #fff;
}
.coverage-group {
  margin-bottom: 16px;
}
.group-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.group-count {
  color: var(--muted);
  font-size: 12px;
}
.scope-links {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
}
.scope-link {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
}
.scope-count {
  color: var(--muted);
  font-size: 12px;
}
.status-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
  line-height: 18px;
}
.tag-已过期 {
  background: #fee4e2;
  color: #b42318;
}
.tag-临期 {
  background: #fef0c7;
  color: #b54708;
}
.tag-有效 {
  background: #dcfae6;
  color: #027a48;
}
.tag-已注销 {
  background: #eaecf0;
  color: #475467;
}
.block-empty {
  display: block;
  padding: 24px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
}
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(16, 24, 40, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
}
.modal-panel {
  width: min(760px, 92vw);
  max-height: 84vh;
  overflow: auto;
  background: #fff;
  border-radius: 10px;
  padding: 16px 20px;
}
.modal-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 10px;
}
.modal-head h3 {
  margin: 0 0 4px;
  font-size: 16px;
}
.modal-sub {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
}
.scope-summary {
  font-size: 13px;
}
.covered-text {
  color: #027a48;
}
.uncovered-text {
  color: #b42318;
}
.row-uncovered {
  background: #fff8f7;
}
</style>
