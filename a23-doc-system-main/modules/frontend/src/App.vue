<script setup lang="ts">
import { ref } from 'vue'
import Header from '@/layout/Header.vue'
import Sidebar from '@/layout/Sidebar.vue'
import MainContent from '@/layout/MainContent.vue'

const currentTab = ref(0)
</script>

<template>
  <div class="min-h-screen bg-bg">
    <Header />
    <div class="flex h-[calc(100vh-56px)]">
      <Sidebar v-model="currentTab" />
      <MainContent :tab="currentTab" />
    </div>
  </div>
</template>

<style scoped>
</style>
