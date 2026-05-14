<template>
  <div class="app-container">
    <Sidebar />
    <div class="main-content">
      <router-view />
    </div>
  </div>
</template>

<script setup>
import Sidebar from './components/Sidebar.vue'
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body, #app { height: 100%; font-family: 'Helvetica Neue', Arial, sans-serif; }
.app-container { display: flex; height: 100vh; }
.main-content { flex: 1; padding: 24px; overflow-y: auto; background: #f5f7fa; }
</style>
