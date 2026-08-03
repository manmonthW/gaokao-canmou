<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuth } from '@/composables/useAuth'

const router = useRouter()
const route = useRoute()
const auth = useAuth()

const mode = ref<'login' | 'register'>(
  route.query.mode === 'register' ? 'register' : 'login',
)
const loading = ref(false)
const error = ref<string | null>(null)

const loginForm = reactive({ login: '', password: '' })
const regForm = reactive({ email: '', username: '', password: '', confirm: '' })

function redirectAfter() {
  const to = (route.query.redirect as string) || '/'
  router.push(to)
}

async function onLogin() {
  error.value = null
  if (!loginForm.login.trim() || !loginForm.password) {
    error.value = '请输入邮箱/用户名与密码'
    return
  }
  loading.value = true
  try {
    await auth.login(loginForm.login.trim(), loginForm.password)
    ElMessage.success('登录成功，已同步你的方案')
    redirectAfter()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

async function onRegister() {
  error.value = null
  if (!regForm.email.trim() || !regForm.username.trim() || !regForm.password) {
    error.value = '请完整填写邮箱、用户名与密码'
    return
  }
  if (regForm.password.length < 8) {
    error.value = '密码至少 8 位'
    return
  }
  if (regForm.password !== regForm.confirm) {
    error.value = '两次输入的密码不一致'
    return
  }
  loading.value = true
  try {
    await auth.register(regForm.email.trim(), regForm.username.trim(), regForm.password)
    ElMessage.success('注册成功，已为你创建账号')
    redirectAfter()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

function switchMode(m: 'login' | 'register') {
  mode.value = m
  error.value = null
}
</script>

<template>
  <div class="auth">
    <div class="auth__card">
      <div class="auth__brand">
        <span class="auth__mark">辽</span>
        <span class="auth__name">辽宁志愿参谋</span>
      </div>

      <div class="auth__tabs">
        <button :class="{ active: mode === 'login' }" @click="switchMode('login')">登录</button>
        <button :class="{ active: mode === 'register' }" @click="switchMode('register')">注册</button>
      </div>

      <el-alert v-if="error" type="error" :title="error" show-icon :closable="false" class="auth__err" />

      <!-- 登录 -->
      <form v-if="mode === 'login'" class="auth__form" @submit.prevent="onLogin">
        <label class="fld">
          <span class="fld__k">邮箱或用户名</span>
          <el-input v-model="loginForm.login" placeholder="邮箱或用户名" size="large" />
        </label>
        <label class="fld">
          <span class="fld__k">密码</span>
          <el-input v-model="loginForm.password" type="password" placeholder="密码" size="large" show-password @keyup.enter="onLogin" />
        </label>
        <el-button type="primary" size="large" :loading="loading" class="auth__submit" @click="onLogin">登录</el-button>
        <p class="auth__switch">还没有账号？<a @click="switchMode('register')">立即注册</a></p>
      </form>

      <!-- 注册 -->
      <form v-else class="auth__form" @submit.prevent="onRegister">
        <label class="fld">
          <span class="fld__k">邮箱</span>
          <el-input v-model="regForm.email" placeholder="用于登录与找回，如 you@example.com" size="large" />
        </label>
        <label class="fld">
          <span class="fld__k">用户名</span>
          <el-input v-model="regForm.username" placeholder="2–32 位，字母/数字/中文/下划线" size="large" />
        </label>
        <label class="fld">
          <span class="fld__k">密码</span>
          <el-input v-model="regForm.password" type="password" placeholder="至少 8 位" size="large" show-password />
        </label>
        <label class="fld">
          <span class="fld__k">确认密码</span>
          <el-input v-model="regForm.confirm" type="password" placeholder="再次输入密码" size="large" show-password @keyup.enter="onRegister" />
        </label>
        <el-button type="primary" size="large" :loading="loading" class="auth__submit" @click="onRegister">注册并登录</el-button>
        <p class="auth__switch">已有账号？<a @click="switchMode('login')">去登录</a></p>
      </form>

      <p class="auth__note">
        登录后你的考生档案与志愿方案会保存到账号，换设备也能继续。
        未登录时数据仅保存在本机浏览器。
      </p>
    </div>
  </div>
</template>

<style scoped>
.auth {
  min-height: 60vh;
  display: grid;
  place-items: center;
  padding: var(--space-6) var(--space-4);
}
.auth__card {
  width: 100%;
  max-width: 420px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  padding: var(--space-6);
}
.auth__brand { display: flex; align-items: center; gap: var(--space-2); justify-content: center; margin-bottom: var(--space-5); }
.auth__mark { width: 34px; height: 34px; border-radius: var(--radius-sm); background: var(--color-primary); color: #fff; display: grid; place-items: center; font-weight: 700; }
.auth__name { font-size: var(--text-lg); font-weight: 600; }
.auth__tabs { display: flex; gap: var(--space-2); margin-bottom: var(--space-5); border-bottom: 1px solid var(--color-border); }
.auth__tabs button {
  flex: 1; padding: var(--space-3); background: none; border: none; cursor: pointer;
  font-size: var(--text-base); color: var(--color-text-secondary);
  border-bottom: 2px solid transparent; margin-bottom: -1px;
}
.auth__tabs button.active { color: var(--color-primary); border-bottom-color: var(--color-primary); font-weight: 600; }
.auth__err { margin-bottom: var(--space-4); }
.auth__form { display: flex; flex-direction: column; gap: var(--space-4); }
.fld { display: flex; flex-direction: column; gap: var(--space-2); }
.fld__k { font-size: var(--text-sm); color: var(--color-text-secondary); }
.auth__submit { width: 100%; margin-top: var(--space-2); }
.auth__switch { text-align: center; font-size: var(--text-sm); color: var(--color-text-muted); margin: 0; }
.auth__switch a { cursor: pointer; color: var(--color-primary); }
.auth__note { margin: var(--space-5) 0 0; font-size: var(--text-xs); color: var(--color-text-muted); line-height: 1.7; text-align: center; }
</style>
