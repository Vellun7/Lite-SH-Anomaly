<template>
  <div class="device-management">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left"></div>
      <div class="header-right"></div>
    </div>

    <!-- 主布局：分组侧边栏 + 设备展示区 -->
    <div class="main-layout">
      <!-- 左侧：分组侧边栏 -->
      <aside class="group-sidebar">
        <div class="sidebar-header">
          <h3>设备分组</h3>
        </div>
        <div class="group-list">
          <div
            v-for="group in sidebarGroups"
            :key="group.key"
            class="group-item"
            :class="{ active: selectedGroupId === group.id }"
            @click="onGroupChange(group.id)"
          >
            <el-icon>
              <Box v-if="group.isUngrouped" />
              <Folder v-else />
            </el-icon>
            <span class="group-name">{{ group.name }}</span>
            <span class="group-count">{{ group.device_count }}</span>
            <el-dropdown
              trigger="click"
              :disabled="group.isUngrouped"
              @command="(cmd: string) => handleGroupAction(cmd, group)"
              @click.stop
            >
              <el-button
                class="group-more-btn"
                :class="{ 'is-placeholder': group.isUngrouped }"
                text
                circle
                size="small"
              >
                <el-icon><MoreFilled /></el-icon>
              </el-button>
              <template v-if="!group.isUngrouped" #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="add-device">
                    <el-icon><Plus /></el-icon>
                    添加设备
                  </el-dropdown-item>
                  <el-dropdown-item command="rename" divided>
                    <el-icon><Edit /></el-icon>
                    重命名
                  </el-dropdown-item>
                  <el-dropdown-item command="delete">
                    <el-icon><Delete /></el-icon>
                    删除分组
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
        <!-- 新建分组 -->
        <div class="create-group-section">
          <div v-if="!showCreateGroupInput" class="create-group-btn" @click="showCreateGroupInput = true">
            <el-icon><Plus /></el-icon>
            <span>新建分组</span>
          </div>
          <div v-else class="create-group-input">
            <el-input
              ref="newGroupInputRef"
              v-model="newGroupName"
              placeholder="输入分组名称"
              size="small"
              @keyup.enter="handleCreateGroup"
              @blur="cancelCreateGroup"
            />
            <div class="create-group-actions">
              <el-button size="small" type="primary" @click="handleCreateGroup">确定</el-button>
              <el-button size="small" @click="cancelCreateGroup">取消</el-button>
            </div>
          </div>
        </div>
      </aside>

      <!-- 右侧：设备展示区 -->
      <div class="device-area" v-loading="loading">
        <!-- 视图A：选中"全部"时，各分组并排展示 -->
        <template v-if="selectedGroupId === 'all'">
          <div v-for="group in deviceGroups" :key="group.id" class="group-section">
            <div class="group-section-header">
              <h3>{{ group.name }}</h3>
              <span class="group-device-count">{{ getGroupDeviceCount(group.id) }} 台设备</span>
            </div>
            <div class="device-grid">
              <div
                v-for="device in getGroupDevices(group.id)"
                :key="device.device_id"
                class="device-card"
                :class="{ 'is-selected': isSelected(device) }"
                @click="toggleSelect(device, $event)"
              >
                <!-- 卡片头部 -->
                <div class="card-header">
                  <div class="header-left">
                    <div class="device-icon-wrapper" :class="device.status">
                      <el-icon :size="28">
                        <Monitor v-if="device.device_type === 'camera'" />
                        <Lock v-else-if="device.device_type === 'door_lock'" />
                        <Cpu v-else-if="device.device_type === 'sensor'" />
                        <Connection v-else-if="device.device_type === 'gateway'" />
                        <Box v-else />
                      </el-icon>
                      <div class="status-indicator" :class="device.status"></div>
                    </div>
                  </div>
                  <div class="device-title">
                    <h4>{{ device.name }}</h4>
                    <span class="device-type">{{ device.device_type_display }}</span>
                  </div>
                  <el-dropdown trigger="click" @command="(cmd: string) => handleCardAction(cmd, device)">
                    <el-button class="more-btn" text circle @click.stop>
                      <el-icon><MoreFilled /></el-icon>
                    </el-button>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item command="detail">
                          <el-icon><View /></el-icon>
                          查看详情
                        </el-dropdown-item>
                        <el-dropdown-item command="edit">
                          <el-icon><Edit /></el-icon>
                          编辑设备
                        </el-dropdown-item>
                        <el-dropdown-item command="delete" divided>
                          <el-icon><Delete /></el-icon>
                          删除设备
                        </el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                </div>
                <!-- 卡片内容 -->
                <div class="card-body">
                  <div class="info-row">
                    <span class="info-label">IP地址</span>
                    <span class="info-value">{{ device.ip_address }}</span>
                  </div>
                  <div class="info-row">
                    <span class="info-label">位置</span>
                    <span class="info-value">{{ device.location || '未设置' }}</span>
                  </div>
                </div>
                <!-- 卡片底部 -->
                <div class="card-footer">
                  <div class="security-gauge">
                    <svg class="gauge-svg" viewBox="0 0 100 100">
                      <circle class="gauge-bg" cx="50" cy="50" r="42" fill="none" stroke-width="8" />
                      <circle
                        class="gauge-progress"
                        :class="device.security_level"
                        cx="50" cy="50" r="42"
                        fill="none" stroke-width="8"
                        stroke-linecap="round"
                        :stroke-dasharray="getGaugeDashArray(device.security_score)"
                        transform="rotate(-90 50 50)"
                      />
                    </svg>
                    <div class="gauge-content">
                      <span class="gauge-score">{{ device.security_score.toFixed(0) }}</span>
                      <span :class="['gauge-level', device.security_level]">
                        {{ getSecurityLevelText(device.security_level) }}
                      </span>
                    </div>
                  </div>
                  <div class="device-meta">
                    <div class="status-badge" :class="device.status">
                      <span class="status-dot"></span>
                      {{ getStatusText(device.status) }}
                    </div>
                    <div class="last-seen">
                      <el-icon><Clock /></el-icon>
                      {{ formatTime(device.last_seen) }}
                    </div>
                  </div>
                </div>
              </div>
              <div v-if="getGroupDevices(group.id).length === 0" class="group-empty">
                暂无设备
              </div>
            </div>
          </div>
          <!-- 未分组（仅当有未分组设备时显示） -->
          <div v-if="ungroupedDevices.length > 0" class="group-section">
            <div class="group-section-header">
              <h3>未分组</h3>
              <span class="group-device-count">{{ ungroupedDevices.length }} 台设备</span>
            </div>
            <div class="device-grid">
              <div
                v-for="device in ungroupedDevices"
                :key="device.device_id"
                class="device-card"
                :class="{ 'is-selected': isSelected(device) }"
                @click="toggleSelect(device, $event)"
              >
                <!-- 卡片头部 -->
                <div class="card-header">
                  <div class="header-left">
                    <div class="device-icon-wrapper" :class="device.status">
                      <el-icon :size="28">
                        <Monitor v-if="device.device_type === 'camera'" />
                        <Lock v-else-if="device.device_type === 'door_lock'" />
                        <Cpu v-else-if="device.device_type === 'sensor'" />
                        <Connection v-else-if="device.device_type === 'gateway'" />
                        <Box v-else />
                      </el-icon>
                      <div class="status-indicator" :class="device.status"></div>
                    </div>
                  </div>
                  <div class="device-title">
                    <h4>{{ device.name }}</h4>
                    <span class="device-type">{{ device.device_type_display }}</span>
                  </div>
                  <el-dropdown trigger="click" @command="(cmd: string) => handleCardAction(cmd, device)">
                    <el-button class="more-btn" text circle @click.stop>
                      <el-icon><MoreFilled /></el-icon>
                    </el-button>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item command="detail">
                          <el-icon><View /></el-icon>
                          查看详情
                        </el-dropdown-item>
                        <el-dropdown-item command="edit">
                          <el-icon><Edit /></el-icon>
                          编辑设备
                        </el-dropdown-item>
                        <el-dropdown-item command="delete" divided>
                          <el-icon><Delete /></el-icon>
                          删除设备
                        </el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                </div>
                <!-- 卡片内容 -->
                <div class="card-body">
                  <div class="info-row">
                    <span class="info-label">IP地址</span>
                    <span class="info-value">{{ device.ip_address }}</span>
                  </div>
                  <div class="info-row">
                    <span class="info-label">位置</span>
                    <span class="info-value">{{ device.location || '未设置' }}</span>
                  </div>
                </div>
                <!-- 卡片底部 -->
                <div class="card-footer">
                  <div class="security-gauge">
                    <svg class="gauge-svg" viewBox="0 0 100 100">
                      <circle class="gauge-bg" cx="50" cy="50" r="42" fill="none" stroke-width="8" />
                      <circle
                        class="gauge-progress"
                        :class="device.security_level"
                        cx="50" cy="50" r="42"
                        fill="none" stroke-width="8"
                        stroke-linecap="round"
                        :stroke-dasharray="getGaugeDashArray(device.security_score)"
                        transform="rotate(-90 50 50)"
                      />
                    </svg>
                    <div class="gauge-content">
                      <span class="gauge-score">{{ device.security_score.toFixed(0) }}</span>
                      <span :class="['gauge-level', device.security_level]">
                        {{ getSecurityLevelText(device.security_level) }}
                      </span>
                    </div>
                  </div>
                  <div class="device-meta">
                    <div class="status-badge" :class="device.status">
                      <span class="status-dot"></span>
                      {{ getStatusText(device.status) }}
                    </div>
                    <div class="last-seen">
                      <el-icon><Clock /></el-icon>
                      {{ formatTime(device.last_seen) }}
                    </div>
                  </div>
                </div>
              </div>
              <div v-if="ungroupedDevices.length === 0" class="group-empty">
                暂无未分组设备
              </div>
            </div>
          </div>
        </template>

        <!-- 视图B：选中单个分组 -->
        <template v-else-if="isSingleGroupView">
          <div class="device-grid">
            <div
              v-for="device in currentGroupDevices"
              :key="device.device_id"
              class="device-card"
              :class="{ 'is-selected': isSelected(device) }"
              @click="toggleSelect(device, $event)"
            >
              <!-- 卡片头部 -->
              <div class="card-header">
                <div class="header-left">
                  <div class="device-icon-wrapper" :class="device.status">
                    <el-icon :size="28">
                      <Monitor v-if="device.device_type === 'camera'" />
                      <Lock v-else-if="device.device_type === 'door_lock'" />
                      <Cpu v-else-if="device.device_type === 'sensor'" />
                      <Connection v-else-if="device.device_type === 'gateway'" />
                      <Box v-else />
                    </el-icon>
                    <div class="status-indicator" :class="device.status"></div>
                  </div>
                </div>
                <div class="device-title">
                  <h4>{{ device.name }}</h4>
                  <span class="device-type">{{ device.device_type_display }}</span>
                </div>
                <el-dropdown trigger="click" @command="(cmd: string) => handleCardAction(cmd, device)">
                  <el-button class="more-btn" text circle @click.stop>
                    <el-icon><MoreFilled /></el-icon>
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="detail">
                        <el-icon><View /></el-icon>
                        查看详情
                      </el-dropdown-item>
                      <el-dropdown-item command="edit">
                        <el-icon><Edit /></el-icon>
                        编辑设备
                      </el-dropdown-item>
                      <el-dropdown-item command="delete" divided>
                        <el-icon><Delete /></el-icon>
                        删除设备
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </div>
              <!-- 卡片内容 -->
              <div class="card-body">
                <div class="info-row">
                  <span class="info-label">IP地址</span>
                  <span class="info-value">{{ device.ip_address }}</span>
                </div>
                <div class="info-row">
                  <span class="info-label">位置</span>
                  <span class="info-value">{{ device.location || '未设置' }}</span>
                </div>
              </div>
              <!-- 卡片底部 -->
              <div class="card-footer">
                <div class="security-gauge">
                  <svg class="gauge-svg" viewBox="0 0 100 100">
                    <circle class="gauge-bg" cx="50" cy="50" r="42" fill="none" stroke-width="8" />
                    <circle
                      class="gauge-progress"
                      :class="device.security_level"
                      cx="50" cy="50" r="42"
                      fill="none" stroke-width="8"
                      stroke-linecap="round"
                      :stroke-dasharray="getGaugeDashArray(device.security_score)"
                      transform="rotate(-90 50 50)"
                    />
                  </svg>
                  <div class="gauge-content">
                    <span class="gauge-score">{{ device.security_score.toFixed(0) }}</span>
                    <span :class="['gauge-level', device.security_level]">
                      {{ getSecurityLevelText(device.security_level) }}
                    </span>
                  </div>
                </div>
                <div class="device-meta">
                  <div class="status-badge" :class="device.status">
                    <span class="status-dot"></span>
                    {{ getStatusText(device.status) }}
                  </div>
                  <div class="last-seen">
                    <el-icon><Clock /></el-icon>
                    {{ formatTime(device.last_seen) }}
                  </div>
                </div>
              </div>
            </div>
            <div v-if="currentGroupDevices.length === 0" class="empty-state">
              <el-icon :size="64"><Box /></el-icon>
              <h3>暂无设备</h3>
              <p>该分组暂无设备</p>
            </div>
          </div>
        </template>

        <!-- 视图C：选中"未分组" -->
        <template v-else-if="selectedGroupId === 'ungrouped'">
          <div class="device-grid">
            <div
              v-for="device in ungroupedDevices"
              :key="device.device_id"
              class="device-card"
              :class="{ 'is-selected': isSelected(device) }"
              @click="toggleSelect(device, $event)"
            >
              <!-- 卡片头部 -->
              <div class="card-header">
                <div class="header-left">
                  <div class="device-icon-wrapper" :class="device.status">
                    <el-icon :size="28">
                      <Monitor v-if="device.device_type === 'camera'" />
                      <Lock v-else-if="device.device_type === 'door_lock'" />
                      <Cpu v-else-if="device.device_type === 'sensor'" />
                      <Connection v-else-if="device.device_type === 'gateway'" />
                      <Box v-else />
                    </el-icon>
                    <div class="status-indicator" :class="device.status"></div>
                  </div>
                </div>
                <div class="device-title">
                  <h4>{{ device.name }}</h4>
                  <span class="device-type">{{ device.device_type_display }}</span>
                </div>
                <el-dropdown trigger="click" @command="(cmd: string) => handleCardAction(cmd, device)">
                  <el-button class="more-btn" text circle @click.stop>
                    <el-icon><MoreFilled /></el-icon>
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="detail">
                        <el-icon><View /></el-icon>
                        查看详情
                      </el-dropdown-item>
                      <el-dropdown-item command="edit">
                        <el-icon><Edit /></el-icon>
                        编辑设备
                      </el-dropdown-item>
                      <el-dropdown-item command="delete" divided>
                        <el-icon><Delete /></el-icon>
                        删除设备
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </div>
              <!-- 卡片内容 -->
              <div class="card-body">
                <div class="info-row">
                  <span class="info-label">IP地址</span>
                  <span class="info-value">{{ device.ip_address }}</span>
                </div>
                <div class="info-row">
                  <span class="info-label">位置</span>
                  <span class="info-value">{{ device.location || '未设置' }}</span>
                </div>
              </div>
              <!-- 卡片底部 -->
              <div class="card-footer">
                <div class="security-gauge">
                  <svg class="gauge-svg" viewBox="0 0 100 100">
                    <circle class="gauge-bg" cx="50" cy="50" r="42" fill="none" stroke-width="8" />
                    <circle
                      class="gauge-progress"
                      :class="device.security_level"
                      cx="50" cy="50" r="42"
                      fill="none" stroke-width="8"
                      stroke-linecap="round"
                      :stroke-dasharray="getGaugeDashArray(device.security_score)"
                      transform="rotate(-90 50 50)"
                    />
                  </svg>
                  <div class="gauge-content">
                    <span class="gauge-score">{{ device.security_score.toFixed(0) }}</span>
                    <span :class="['gauge-level', device.security_level]">
                      {{ getSecurityLevelText(device.security_level) }}
                    </span>
                  </div>
                </div>
                <div class="device-meta">
                  <div class="status-badge" :class="device.status">
                    <span class="status-dot"></span>
                    {{ getStatusText(device.status) }}
                  </div>
                  <div class="last-seen">
                    <el-icon><Clock /></el-icon>
                    {{ formatTime(device.last_seen) }}
                  </div>
                </div>
              </div>
            </div>
            <div v-if="ungroupedDevices.length === 0" class="empty-state">
              <el-icon :size="64"><Box /></el-icon>
              <h3>暂无未分组设备</h3>
              <p>所有设备都已分组</p>
            </div>
          </div>
        </template>
      </div>
    </div>

    <!-- 批量操作栏 -->
    <Transition name="batch-bar">
      <div v-if="selectedDevices.length > 0" class="batch-actions">
        <div class="batch-left">
          <el-checkbox
            :model-value="isAllSelected"
            :indeterminate="isIndeterminate"
            @change="handleSelectAll"
          >
            全选
          </el-checkbox>
          <div class="batch-info">
            <span class="count">{{ selectedDevices.length }}</span>
            <span class="text">个设备已选中</span>
          </div>
          <el-button text @click="clearSelection">取消选择</el-button>
        </div>
        <div class="batch-buttons">
          <el-dropdown trigger="click" @command="handleBatchGroup">
            <el-button>
              <el-icon><FolderAdd /></el-icon>
              批量分组
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item
                  v-for="group in deviceGroups"
                  :key="group.id"
                  :command="group.id"
                >
                  {{ group.name }}
                </el-dropdown-item>
                <el-dropdown-item v-if="deviceGroups.length === 0" disabled>
                  暂无分组
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-button type="danger" @click="batchDelete" :loading="batchLoading.delete">
            <el-icon><Delete /></el-icon>
            批量删除
          </el-button>
        </div>
      </div>
    </Transition>

    <!-- 设备详情对话框 -->
    <DeviceDetailDialog
      v-model="showDeviceDetail"
      :device="currentDevice"
      @refresh="refreshData"
      @edit="editDevice"
    />

    <!-- 设备编辑对话框 -->
    <DeviceEditDialog
      v-model="showDeviceEdit"
      :device="currentDevice"
      @refresh="refreshData"
    />

    <!-- 创建设备对话框 -->
    <DeviceCreateDialog
      v-model="showCreateDevice"
      :default-group-id="defaultCreateGroupId"
      @refresh="refreshData"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Folder, Monitor, Lock, Cpu, Connection, Box,
  MoreFilled, View, Edit, Delete, Clock, FolderAdd, Plus
} from '@element-plus/icons-vue'

import {
  getDevices, getDeviceGroups, getUngroupedDevices, getGroupDevices as getGroupDevicesApi,
  createDeviceGroup, updateDeviceGroup, deleteDeviceGroup,
  deleteDevice, batchUpdateSecurityScores, addDevicesToGroup,
  type Device, type DeviceGroup
} from '@/api/device'

import DeviceDetailDialog from '@/components/device/DeviceDetailDialog.vue'
import DeviceEditDialog from '@/components/device/DeviceEditDialog.vue'
import DeviceCreateDialog from '@/components/device/DeviceCreateDialog.vue'

// ========== 响应式数据 ==========
const loading = ref(false)
const selectedGroupId = ref<string | number>('ungrouped')

// 自动刷新定时器
let autoRefreshTimer: ReturnType<typeof setInterval> | null = null
const AUTO_REFRESH_INTERVAL = 3 * 60 * 60 * 1000 // 3小时

// 批量操作加载状态
const batchLoading = ref({
  delete: false,
  group: false
})

// 创建设备时默认分组
const defaultCreateGroupId = ref<number | null>(null)

// 设备数据
const devices = ref<Device[]>([])
const deviceGroups = ref<DeviceGroup[]>([])
const selectedDevices = ref<Device[]>([])
const ungroupedDevices = ref<Device[]>([])
const currentGroupDevices = ref<Device[]>([])

// 对话框显示状态
const showDeviceDetail = ref(false)
const showDeviceEdit = ref(false)
const showCreateDevice = ref(false)

// 当前操作的设备
const currentDevice = ref<Device | null>(null)

// 新建分组
const showCreateGroupInput = ref(false)
const newGroupName = ref('')

// ========== 计算属性 ==========
const onlineCount = computed(() => devices.value.filter(d => d.status === 'online').length)
const offlineCount = computed(() => devices.value.filter(d => d.status === 'offline').length)
const warningCount = computed(() => devices.value.filter(d => d.status === 'warning').length)

const ungroupedCount = computed(() => ungroupedDevices.value.length)

// 侧边栏分组列表（包含未分组，按设备数量降序排序）
const sidebarGroups = computed(() => {
  const groups = deviceGroups.value.map(g => ({
    ...g,
    key: g.id,
    isUngrouped: false
  }))

  // 添加未分组虚拟分组
  groups.push({
    id: 'ungrouped',
    key: 'ungrouped',
    name: '未分组',
    device_count: ungroupedCount.value,
    description: '',
    icon: '',
    color: '',
    parent: null,
    parent_name: null,
    created_at: '',
    updated_at: '',
    isUngrouped: true
  } as any)

  // 按设备数量降序排序
  return groups.sort((a, b) => b.device_count - a.device_count)
})

// 是否展示单个分组视图（selectedGroupId 是 number 类型）
const isSingleGroupView = computed(() => typeof selectedGroupId.value === 'number')

// 是否选中
const isSelected = (device: Device) => {
  return selectedDevices.value.some(d => d.device_id === device.device_id)
}

// 切换选中
const toggleSelect = (device: Device, event: MouseEvent) => {
  const target = event.target as HTMLElement
  if (target.closest('.el-dropdown')) return

  const index = selectedDevices.value.findIndex(d => d.device_id === device.device_id)
  if (index === -1) {
    selectedDevices.value.push(device)
  } else {
    selectedDevices.value.splice(index, 1)
  }
}

// 获取当前展示的设备列表
const getCurrentDisplayDevices = (): Device[] => {
  if (selectedGroupId.value === 'ungrouped') {
    return ungroupedDevices.value
  } else {
    return currentGroupDevices.value
  }
}

// 全选相关
const isAllSelected = computed(() => {
  const current = getCurrentDisplayDevices()
  return selectedDevices.value.length > 0 && selectedDevices.value.length === current.length
})

const isIndeterminate = computed(() => {
  const current = getCurrentDisplayDevices()
  return selectedDevices.value.length > 0 && selectedDevices.value.length < current.length
})

// 全选/取消全选
const handleSelectAll = (val: boolean | string | number) => {
  const current = getCurrentDisplayDevices()
  if (val) {
    selectedDevices.value = [...current]
  } else {
    selectedDevices.value = []
  }
}

// 取消选择
const clearSelection = () => {
  selectedDevices.value = []
}

// 获取分组下的设备（用于"全部"视图）
const getGroupDevices = (groupId: number): Device[] => {
  return devices.value.filter(d => d.group_ids?.includes(groupId))
}

const getGroupDeviceCount = (groupId: number): number => {
  return devices.value.filter(d => d.group_ids?.includes(groupId)).length
}

// ========== 数据加载 ==========
// 加载设备列表
const loadDevices = async () => {
  loading.value = true
  try {
    const res = await getDevices()
    const raw = res.data as any
    const data = raw.data || raw
    devices.value = data.results || data || []
  } catch (error) {
    console.error('加载设备列表失败:', error)
    ElMessage.error('加载设备列表失败')
  } finally {
    loading.value = false
  }
}

// 加载未分组设备
const loadUngroupedDevices = async () => {
  try {
    const res = await getUngroupedDevices()
    const raw = res.data as any
    const data = raw.data || raw
    ungroupedDevices.value = data.results || data || []
  } catch (error) {
    console.error('加载未分组设备失败:', error)
  }
}

// 加载单个分组下的设备
const loadGroupDevices = async (groupId: number) => {
  try {
    const res = await getGroupDevicesApi(groupId)
    const raw = res.data as any
    const data = raw.data || raw
    currentGroupDevices.value = data.results || data || []
  } catch (error) {
    console.error('加载分组设备失败:', error)
  }
}

// 加载设备分组
const loadGroups = async () => {
  try {
    const res = await getDeviceGroups()
    const raw = res.data as any
    const data = raw.data || raw
    deviceGroups.value = data || []

    // 如果当前选中的是已删除的分组，切换到未分组
    if (selectedGroupId.value !== null && selectedGroupId.value !== 'ungrouped') {
      const exists = deviceGroups.value.some(g => g.id === selectedGroupId.value)
      if (!exists) {
        selectedGroupId.value = 'ungrouped'
      }
    }
  } catch (error) {
    console.error('加载设备分组失败:', error)
  }
}

// 分组选择变化
const onGroupChange = async (groupId: string | number) => {
  selectedGroupId.value = groupId
  clearSelection()
  if (groupId === 'ungrouped') {
    await loadUngroupedDevices()
  } else {
    await loadGroupDevices(groupId as number)
  }
}

// 刷新数据
const refreshData = async () => {
  await Promise.all([loadDevices(), loadGroups()])
  if (selectedGroupId.value === 'ungrouped') {
    await loadUngroupedDevices()
  } else {
    await loadGroupDevices(selectedGroupId.value as number)
  }
}

// ========== 设备操作 ==========
// 卡片操作处理
const handleCardAction = async (command: string, device: Device) => {
  switch (command) {
    case 'detail':
      currentDevice.value = device
      showDeviceDetail.value = true
      break
    case 'edit':
      editDevice(device)
      break
    case 'delete':
      await handleDeleteDevice(device)
      break
  }
}

// 编辑设备
const editDevice = (device: Device) => {
  currentDevice.value = device
  showDeviceEdit.value = true
}

// 删除设备
const handleDeleteDevice = async (device: Device) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除设备 "${device.name}" 吗？此操作不可恢复。`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    await deleteDevice(device.device_id)
    ElMessage.success('设备删除成功')
    refreshData()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除设备失败')
    }
  }
}

// 批量分组
const handleBatchGroup = async (groupId: number) => {
  if (selectedDevices.value.length === 0) return

  batchLoading.value.group = true
  try {
    const deviceIds = selectedDevices.value.map(d => d.device_id)
    await addDevicesToGroup(groupId, deviceIds)

    const groupName = deviceGroups.value.find(g => g.id === groupId)?.name || '分组'
    ElMessage.success(`已将 ${deviceIds.length} 个设备添加到「${groupName}」`)

    clearSelection()
    refreshData()
  } catch (error) {
    ElMessage.error('批量分组失败')
  } finally {
    batchLoading.value.group = false
  }
}

// 打开创建设备对话框（指定默认分组）
const openCreateDeviceDialog = (groupId: number) => {
  defaultCreateGroupId.value = groupId
  showCreateDevice.value = true
}

// 批量删除
const batchDelete = async () => {
  if (selectedDevices.value.length === 0) return

  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedDevices.value.length} 个设备吗？此操作不可恢复。`,
      '确认批量删除',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    batchLoading.value.delete = true
    let success = 0
    let failed = 0

    for (const device of selectedDevices.value) {
      try {
        await deleteDevice(device.device_id)
        success++
      } catch {
        failed++
      }
    }

    if (failed === 0) {
      ElMessage.success(`成功删除 ${success} 个设备`)
    } else {
      ElMessage.warning(`删除完成：成功 ${success} 个，失败 ${failed} 个`)
    }

    clearSelection()
    refreshData()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('批量删除失败')
    }
  } finally {
    batchLoading.value.delete = false
  }
}

// ========== 分组操作 ==========
// 分组右键操作
const handleGroupAction = async (command: string, group: DeviceGroup) => {
  switch (command) {
    case 'add-device':
      openCreateDeviceDialog(group.id)
      break
    case 'rename':
      await handleRenameGroup(group)
      break
    case 'delete':
      await handleDeleteGroup(group)
      break
  }
}

// 重命名分组
const handleRenameGroup = async (group: DeviceGroup) => {
  try {
    const { value } = await ElMessageBox.prompt(
      '请输入新的分组名称',
      '重命名分组',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        inputValue: group.name,
        inputPlaceholder: '分组名称'
      }
    )
    if (!value || !value.trim()) return
    await updateDeviceGroup(group.id, { name: value.trim() })
    ElMessage.success('分组已重命名')
    loadGroups()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('重命名失败')
    }
  }
}

// 删除分组
const handleDeleteGroup = async (group: DeviceGroup) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除分组「${group.name}」吗？分组内的设备不会被删除。`,
      '确认删除分组',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    await deleteDeviceGroup(group.id)
    ElMessage.success('分组已删除')
    if (selectedGroupId.value === group.id) {
      selectedGroupId.value = 'ungrouped'
      loadUngroupedDevices()
    }
    loadGroups()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除分组失败')
    }
  }
}

// 新建分组
const handleCreateGroup = async () => {
  if (!newGroupName.value.trim()) return
  try {
    await createDeviceGroup({ name: newGroupName.value.trim() })
    ElMessage.success('分组已创建')
    newGroupName.value = ''
    showCreateGroupInput.value = false
    loadGroups()
  } catch (error) {
    ElMessage.error('创建分组失败')
  }
}

const cancelCreateGroup = () => {
  newGroupName.value = ''
  showCreateGroupInput.value = false
}

// ========== 工具函数 ==========
// 获取安全等级文本
const getSecurityLevelText = (level: string) => {
  const map: Record<string, string> = {
    high: '安全',
    medium: '中等',
    low: '风险'
  }
  return map[level] || '未知'
}

// 获取状态文本
const getStatusText = (status: string) => {
  const map: Record<string, string> = {
    online: '在线',
    offline: '离线',
    warning: '告警'
  }
  return map[status] || '未知'
}

// 计算环形图dasharray
const getGaugeDashArray = (score: number) => {
  const circumference = 2 * Math.PI * 42
  const progress = (score / 100) * circumference
  return `${progress} ${circumference}`
}

// 格式化时间
const formatTime = (time: string | null) => {
  if (!time) return '从未在线'
  const date = new Date(time)
  const now = new Date()
  const diff = now.getTime() - date.getTime()

  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  if (diff < 604800000) return `${Math.floor(diff / 86400000)}天前`
  return date.toLocaleDateString()
}

// ========== 生命周期 ==========
// 启动自动刷新
const startAutoRefresh = () => {
  if (autoRefreshTimer) clearInterval(autoRefreshTimer)
  autoRefreshTimer = setInterval(async () => {
    try {
      await batchUpdateSecurityScores()
      await loadDevices()
    } catch (error) {
      console.error('自动刷新失败:', error)
    }
  }, AUTO_REFRESH_INTERVAL)
}

// 停止自动刷新
const stopAutoRefresh = () => {
  if (autoRefreshTimer) {
    clearInterval(autoRefreshTimer)
    autoRefreshTimer = null
  }
}

onMounted(async () => {
  // 先加载分组，确定默认展示的分组
  await loadGroups()

  // 设置默认选中的分组为设备数量最多的分组
  if (deviceGroups.value.length > 0) {
    const maxGroup = deviceGroups.value.reduce((max, g) =>
      g.device_count > max.device_count ? g : max
    )
    selectedGroupId.value = maxGroup.id
    await loadGroupDevices(maxGroup.id)
  } else {
    selectedGroupId.value = 'ungrouped'
    await loadUngroupedDevices()
  }

  // 加载所有设备（用于"全部"视图）
  await loadDevices()
  startAutoRefresh()
})

onUnmounted(() => {
  stopAutoRefresh()
})
</script>

<style lang="scss" scoped>
// ===== 页面容器 =====
.device-management {
  display: flex;
  flex-direction: column;
  gap: 20px;
  height: calc(100vh - 40px);
}

// ===== 页面头部 =====
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
  flex-shrink: 0;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.header-right {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
  min-height: 10px;
}

.header-action-btn {
  min-width: 120px;
}

// ===== 主布局：侧边栏 + 设备区 =====
.main-layout {
  display: flex;
  gap: 20px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

// ===== 分组侧边栏 =====
.group-sidebar {
  width: 260px;
  flex-shrink: 0;
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: 16px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-header {
  padding: 16px 20px 12px;
  border-bottom: 1px solid var(--border-color);

  h3 {
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
  }
}

.group-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.group-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  color: var(--text-secondary);
  font-size: 14px;
  position: relative;

  &:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
  }

  &.active {
    background: rgba(91, 141, 239, 0.1);
    color: var(--primary-color);
    font-weight: 600;
  }

  .el-icon {
    font-size: 16px;
    flex-shrink: 0;
  }

  .group-name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .group-count {
    font-size: 12px;
    color: var(--text-muted);
    background: var(--bg-elevated);
    padding: 1px 8px;
    border-radius: 8px;
    flex-shrink: 0;
    min-width: 28px;
    text-align: center;
  }

  .group-more-btn {
    opacity: 0;
    transition: opacity 0.2s;
    flex-shrink: 0;

    &.is-placeholder {
      opacity: 0 !important;
      pointer-events: none;
    }
  }

  &:hover .group-more-btn:not(.is-placeholder) {
    opacity: 1;
  }
}

.create-group-section {
  padding: 12px;
  border-top: 1px solid var(--border-color);
}

.create-group-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 10px;
  cursor: pointer;
  color: var(--text-muted);
  font-size: 13px;
  transition: all 0.2s;

  &:hover {
    background: var(--bg-hover);
    color: var(--primary-color);
  }

  .el-icon {
    font-size: 14px;
  }
}

.create-group-input {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.create-group-actions {
  display: flex;
  gap: 6px;
}

// ===== 设备展示区 =====
.device-area {
  flex: 1;
  overflow-y: auto;
  min-width: 0;
}

// "全部"视图：各分组并排
.group-section {
  margin-bottom: 24px;
}

.group-section-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-color);

  h3 {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
  }

  .group-device-count {
    font-size: 12px;
    color: var(--text-muted);
  }
}

.group-empty {
  color: var(--text-muted);
  font-size: 14px;
  padding: 20px;
  text-align: center;
}

// ===== 设备卡片网格 =====
.device-grid {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 16px;
  min-height: 200px;

  .device-card {
    width: 300px;
    flex-shrink: 0;
  }

  .empty-state {
    width: 100%;
  }
}

.device-card {
  position: relative;
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: 16px;
  padding: 20px;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;

  &:hover {
    transform: translateY(-4px);
    border-color: rgba(91, 141, 239, 0.3);
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.3);
  }

  &.is-selected {
    border-color: var(--primary-color);
    background: rgba(91, 141, 239, 0.05);
  }
}

// ===== 卡片头部 =====
.card-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 16px;
}

.header-left {
  flex-shrink: 0;
}

.device-icon-wrapper {
  position: relative;
  width: 52px;
  height: 52px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.3s;

  &.online {
    background: rgba(94, 196, 158, 0.12);
    color: var(--success-color);
  }
  &.offline {
    background: var(--bg-elevated);
    color: var(--text-muted);
  }
  &.warning {
    background: rgba(224, 168, 84, 0.12);
    color: var(--warning-color);
  }
}

.status-indicator {
  position: absolute;
  bottom: -2px;
  right: -2px;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 2px solid var(--card-bg);
  z-index: 2;

  &.online {
    background: var(--success-color);
    box-shadow: 0 0 6px var(--success-color);
  }
  &.offline {
    background: var(--text-muted);
  }
  &.warning {
    background: var(--warning-color);
    box-shadow: 0 0 6px var(--warning-color);
    animation: pulse-warning-dot 1s ease-in-out infinite;
  }
}

.device-title {
  flex: 1;
  min-width: 0;

  h4 {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0 0 4px 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .device-type {
    font-size: 12px;
    color: var(--text-muted);
  }
}

.more-btn {
  color: var(--text-muted);

  &:hover {
    color: var(--text-primary);
    background: var(--bg-hover);
  }
}

// ===== 卡片内容 =====
.card-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-color);
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;

  .info-label {
    font-size: 13px;
    color: var(--text-muted);
  }

  .info-value {
    font-size: 13px;
    color: var(--text-secondary);
    display: flex;
    align-items: center;
    gap: 4px;
  }
}

// ===== 卡片底部：安全评分 =====
.card-footer {
  display: flex;
  align-items: center;
  gap: 20px;
}

.security-gauge {
  position: relative;
  width: 90px;
  height: 90px;
  flex-shrink: 0;
}

.gauge-svg {
  width: 100%;
  height: 100%;
  transform: rotate(0deg);
}

.gauge-bg {
  stroke: var(--bg-elevated);
}

.gauge-progress {
  transition: stroke-dasharray 0.8s ease;

  &.high { stroke: var(--success-color); }
  &.medium { stroke: var(--warning-color); }
  &.low { stroke: var(--danger-color); }
}

.gauge-content {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
}

.gauge-score {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  font-family: var(--font-mono);
  line-height: 1;
}

.gauge-level {
  font-size: 10px;
  font-weight: 600;
  margin-top: 2px;

  &.high { color: var(--success-color); }
  &.medium { color: var(--warning-color); }
  &.low { color: var(--danger-color); }
}

.device-meta {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 12px;
  width: fit-content;

  .status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
  }

  &.online {
    background: rgba(94, 196, 158, 0.12);
    color: var(--success-color);
    .status-dot { background: var(--success-color); }
  }
  &.offline {
    background: var(--bg-elevated);
    color: var(--text-muted);
    .status-dot { background: var(--text-muted); }
  }
  &.warning {
    background: rgba(224, 168, 84, 0.12);
    color: var(--warning-color);
    .status-dot {
      background: var(--warning-color);
      animation: pulse-warning-dot 1s ease-in-out infinite;
    }
  }
}

.last-seen {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-muted);

  .el-icon {
    font-size: 14px;
  }
}

// ===== 脉冲动画 =====
@keyframes pulse-warning-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

// ===== 空状态 =====
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: var(--text-muted);
  min-height: 400px;
  width: 100%;

  .el-icon {
    margin-bottom: 16px;
    opacity: 0.3;
  }

  h3 {
    font-size: 18px;
    font-weight: 600;
    color: var(--text-secondary);
    margin: 0 0 8px 0;
  }

  p {
    font-size: 14px;
    margin: 0 0 20px 0;
  }
}

// ===== 批量操作栏 =====
.batch-actions {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--bg-elevated);
  border: 1px solid var(--border-color);
  padding: 14px 24px;
  border-radius: 16px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 32px;
  z-index: 1000;
  min-width: 500px;
  backdrop-filter: blur(20px);
}

.batch-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.batch-info {
  display: flex;
  align-items: baseline;
  gap: 4px;

  .count {
    font-size: 20px;
    font-weight: 700;
    color: var(--primary-color);
    font-family: var(--font-mono);
  }

  .text {
    color: var(--text-secondary);
    font-size: 14px;
  }
}

.batch-buttons {
  display: flex;
  gap: 10px;
}

// ===== 批量操作栏动画 =====
.batch-bar-enter-active {
  animation: batch-bar-in 0.3s ease-out;
}

.batch-bar-leave-active {
  animation: batch-bar-out 0.2s ease-in;
}

@keyframes batch-bar-in {
  0% {
    opacity: 0;
    transform: translateX(-50%) translateY(20px);
  }
  100% {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
}

@keyframes batch-bar-out {
  0% {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
  100% {
    opacity: 0;
    transform: translateX(-50%) translateY(20px);
  }
}

// ===== 响应式 =====
@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .main-layout {
    flex-direction: column;
  }

  .group-sidebar {
    width: 100%;
    max-height: 200px;
  }

  .device-grid {
    grid-template-columns: 1fr;
  }

  .batch-actions {
    min-width: auto;
    width: calc(100% - 32px);
    flex-direction: column;
    gap: 12px;
  }

  .batch-buttons {
    flex-wrap: wrap;
    justify-content: center;
  }
}
</style>
