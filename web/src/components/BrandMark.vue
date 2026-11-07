<script setup>
/**
 * 品牌头像：使用手绘插画作为统一标识（侧边栏 / 登录页 / 游戏入口）。
 * 图片放在 public/brand.jpg，构建后按站点根路径访问。
 */
defineProps({
  size: { type: Number, default: 42 }
})
</script>

<template>
  <span class="brand-mark" :style="{ width: size + 'px', height: size + 'px' }">
    <img src="/brand.jpg" alt="星星的孩子" />
  </span>
</template>
