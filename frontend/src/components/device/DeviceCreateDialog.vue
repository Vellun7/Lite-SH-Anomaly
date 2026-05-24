<template>
  <DeviceEditDialog
    v-model="visible"
    :device="null"
    :default-group-id="defaultGroupId"
    @refresh="$emit('refresh')"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import DeviceEditDialog from './DeviceEditDialog.vue'

// Props
interface Props {
  modelValue: boolean
  defaultGroupId?: number | null
}

// Emits
interface Emits {
  (e: 'update:modelValue', value: boolean): void
  (e: 'refresh'): void
}

const props = withDefaults(defineProps<Props>(), {
  defaultGroupId: null
})
const emit = defineEmits<Emits>()

// 计算属性
const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})
</script>