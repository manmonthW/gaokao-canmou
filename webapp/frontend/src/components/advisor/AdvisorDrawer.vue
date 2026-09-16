<script setup lang="ts">
import { computed } from 'vue'
import AdvisorPanel from './AdvisorPanel.vue'

const props = withDefaults(defineProps<{ modelValue: boolean; mode?: string; initialQuestion?: string; pageContext?: Record<string, unknown> }>(), {
  mode: '问答', initialQuestion: '', pageContext: () => ({}),
})
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()
const visible = computed({ get: () => props.modelValue, set: (value) => emit('update:modelValue', value) })
</script>

<template>
  <el-drawer v-model="visible" size="min(560px, 100vw)" :with-header="false" destroy-on-close>
    <AdvisorPanel :mode="mode" :initial-question="initialQuestion" :page-context="pageContext" />
  </el-drawer>
</template>
