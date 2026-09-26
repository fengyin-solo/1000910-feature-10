<template>
  <section class="page" data-module="certification">
    <header class="page-head">
      <div>
        <h2>认证认可管理</h2>
        <p class="page-desc">维护资质认定，围绕认定编号、认定类型、发证机构、认定范围做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记资质认定</button>
        <button v-if="view === 'ledger'" class="btn" type="button" @click="exportRows">导出认证认可清单</button>
        <button v-else class="btn" type="button" @click="exportCoverage">导出资质清单</button>
      </div>
    </header>

    <div class="view-tabs">
      <button
        type="button"
        class="tab"
        :class="{ active: view === 'ledger' }"
        @click="switchView('ledger')"
      >
        资质台账
      </button>
      <button
        type="button"
        class="tab"
        :class="{ active: view === 'coverage' }"
        @click="switchView('coverage')"
      >
        资质覆盖视图
      </button>
    </div>

    <template v-if="view === 'ledger'">
      <div class="stat-row">
        <article v-for="item in stats" :key="item.label" class="stat-card">
          <span class="stat-label">{{ item.label }}</span>
          <strong class="stat-value">{{ item.value }}</strong>
        </article>
      </div>

      <form class="filter-bar" @submit.prevent="reload">
        <label v-for="field in filterFields" :key="field" class="filter-item">
          <span>{{ field }}</span>
          <input v-model="filters[field]" :placeholder="`按${field}检索`" />
        </label>
        <button class="btn" type="submit">查询</button>
        <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
      </form>

      <table class="data-table">
        <thead>
          <tr>
            <th v-for="column in columns" :key="column">{{ column }}</th>
            <th>可执行动作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="String(row.id)">
            <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
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
          <tr v-if="!rows.length">
            <td :colspan="columns.length + 1" class="empty-state">暂无认证认可数据，可先登记资质认定</td>
          </tr>
        </tbody>
      </table>

      <footer class="page-foot">
        <span>共 {{ total }} 条认证认可记录</span>
        <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      </footer>
    </template>

    <template v-else>
      <div class="filter-bar">
        <label class="filter-item">
          <span>认定类型</span>
          <select v-model="coverageType" @change="reloadCoverage">
            <option value="">全部类型</option>
            <option v-for="type in coverageTypes" :key="type" :value="type">{{ type }}</option>
          </select>
        </label>
      </div>

      <p v-if="uncoveredProjects.length" class="coverage-hint">
        暂无覆盖：{{ uncoveredProjects.join('、') }}（当前没有有效或临期的资质覆盖这些项目）
      </p>

      <table class="data-table">
        <thead>
          <tr>
            <th>认定编号</th>
            <th>认定范围</th>
            <th>发证机构</th>
            <th>获证日期</th>
            <th>有效期至</th>
            <th>认定状态</th>
            <th>覆盖项目数</th>
            <th>范围明细</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in coverageRows"
            :key="row.id"
            :class="{ 'urgent-row': row.认定状态 === '临期' || row.认定状态 === '已过期' }"
          >
            <td>{{ row.认定编号 }}</td>
            <td>{{ row.认定范围 }}</td>
            <td>{{ row.发证机构 }}</td>
            <td>{{ row.获证日期 }}</td>
            <td>{{ row.有效期至 }}</td>
            <td>{{ row.认定状态 }}</td>
            <td>{{ row.覆盖项目数 }}</td>
            <td>
              <button class="link" type="button" @click="openDetail(row)">查看项目</button>
            </td>
          </tr>
          <tr v-if="!coverageRows.length">
            <td colspan="8" class="empty-state">当前认定类型下暂无资质认定记录</td>
          </tr>
        </tbody>
      </table>

      <div v-if="detail" class="coverage-detail">
        <header class="coverage-detail-head">
          <h3>{{ detail.entry.认定编号 }} · {{ detail.entry.认定范围 }}</h3>
          <button class="link" type="button" @click="detail = null">收起</button>
        </header>
        <p class="coverage-meta">
          发证机构：{{ detail.entry.发证机构 }} · 获证日期：{{ detail.entry.获证日期 }} · 有效期至：{{ detail.entry.有效期至 }} · 认定状态：{{ detail.entry.认定状态 }}
        </p>
        <p v-if="!detail.active" class="error-text">该资质当前不具备开展效力，登记项目暂不可开展。</p>
        <table class="data-table">
          <thead>
            <tr>
              <th>检测项目</th>
              <th>覆盖情况</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="project in detail.projects" :key="project.name">
              <td>{{ project.name }}</td>
              <td v-if="project.covered">可开展</td>
              <td v-else class="muted">暂无覆盖</td>
            </tr>
            <tr v-if="!detail.projects.length">
              <td colspan="2" class="empty-state">暂无检测项目目录</td>
            </tr>
          </tbody>
        </table>
        <p class="coverage-meta">
          可开展 {{ detail.covered_count }} 项，暂无覆盖 {{ detail.uncovered_count }} 项
        </p>
      </div>

      <footer class="page-foot">
        <span>共 {{ coverageTotal }} 条资质认定，临期与已过期排在前面</span>
        <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      </footer>
    </template>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

type CoverageRow = {
  id: number
  认定编号: string
  认定类型: string
  认定范围: string
  发证机构: string
  获证日期: string
  有效期至: string
  认定状态: string
  覆盖项目: string[]
  覆盖项目数: number
}

type CoverageDetail = {
  entry: CoverageRow
  active: boolean
  projects: { name: string; covered: boolean }[]
  covered_count: number
  uncovered_count: number
}

const ENDPOINT = '/api/certification'
const columns = ["认定编号", "认定类型", "发证机构", "认定范围", "获证日期", "有效期至", "证书编号", "认定状态"]
const actions = ["续证申请", "登记过期", "注销证书"]
const statuses = ["有效", "临期", "已过期", "已注销"]
const stats = [{"label": "有效证书", "value": 0}, {"label": "临期证书", "value": 0}, {"label": "过期证书", "value": 0}]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

const view = ref<'ledger' | 'coverage'>('ledger')
const coverageRows = ref<CoverageRow[]>([])
const coverageTotal = ref(0)
const coverageTypes = ref<string[]>([])
const coverageType = ref('')
const uncoveredProjects = ref<string[]>([])
const detail = ref<CoverageDetail | null>(null)

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function exportCoverage() {
  const query = new URLSearchParams({ view: 'coverage' })
  if (coverageType.value) {
    query.set('cert_type', coverageType.value)
  }
  window.open(`${ENDPOINT}/export?${query.toString()}`, '_blank')
}

function openCreate() {
  errorMessage.value = '资质认定登记入口尚未接入审批流'
}

function switchView(next: 'ledger' | 'coverage') {
  view.value = next
  errorMessage.value = ''
  if (next === 'coverage') {
    void reloadCoverage()
  }
}

async function runAction(action: string, row: Row) {
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

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('资质认定列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '认证认可列表读取失败'
  }
}

async function reloadCoverage() {
  errorMessage.value = ''
  detail.value = null
  const query = new URLSearchParams()
  if (coverageType.value) {
    query.set('cert_type', coverageType.value)
  }
  try {
    const response = await request(`${ENDPOINT}/coverage?${query.toString()}`)
    if (!response.ok) {
      throw new Error('资质覆盖视图读取失败')
    }
    const payload = await response.json()
    coverageRows.value = payload.items ?? []
    coverageTotal.value = payload.total ?? coverageRows.value.length
    coverageTypes.value = payload.types ?? []
    uncoveredProjects.value = payload.uncovered_projects ?? []
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '资质覆盖视图读取失败'
  }
}

async function openDetail(row: CoverageRow) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/coverage/${row.id}`)
    if (!response.ok) {
      throw new Error('认定范围明细读取失败')
    }
    detail.value = (await response.json()) as CoverageDetail
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '认定范围明细读取失败'
  }
}

onMounted(reload)
</script>
