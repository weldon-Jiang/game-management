<template>
  <div class="data-table-container">
    <el-table
      v-loading="loading"
      :data="data"
      :stripe="stripe"
      :border="border"
      :size="size"
      @sort-change="handleSortChange"
      v-bind="$attrs"
    >
      <slot></slot>

      <el-table-column v-if="showIndex" label="序号" width="60" align="center">
        <template #default="{ $index }">
          {{ (currentPage - 1) * pageSize + $index + 1 }}
        </template>
      </el-table-column>

      <slot name="columns"></slot>
    </el-table>

    <div class="pagination-container" v-if="showPagination">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="pageSizes"
        :layout="paginationLayout"
        :background="background"
        @current-change="handlePageChange"
        @size-change="handleSizeChange"
      />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  data: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  },
  total: {
    type: Number,
    default: 0
  },
  page: {
    type: Number,
    default: 1
  },
  pageSize: {
    type: Number,
    default: 10
  },
  pageSizes: {
    type: Array,
    default: () => [10, 20, 50, 100]
  },
  showIndex: {
    type: Boolean,
    default: true
  },
  showPagination: {
    type: Boolean,
    default: true
  },
  stripe: {
    type: Boolean,
    default: true
  },
  border: {
    type: Boolean,
    default: true
  },
  size: {
    type: String,
    default: 'default'
  },
  background: {
    type: Boolean,
    default: true
  },
  paginationLayout: {
    type: String,
    default: 'total, sizes, prev, pager, next, jumper'
  }
})

const emit = defineEmits(['page-change', 'size-change', 'sort-change', 'update:page', 'update:pageSize'])

const currentPage = computed({
  get: () => props.page,
  set: (val) => emit('update:page', val)
})

const pageSize = computed({
  get: () => props.pageSize,
  set: (val) => emit('update:pageSize', val)
})

function handlePageChange(page) {
  emit('page-change', page)
}

function handleSizeChange(size) {
  emit('size-change', size)
}

function handleSortChange({ prop, order }) {
  emit('sort-change', { prop, order })
}
</script>

<style scoped>
.data-table-container {
  width: 100%;
}

.pagination-container {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
  padding: 8px 0;
}
</style>
