<script setup>
/**
 * 道具手绘库。
 *
 * 坐标约定：原点 (0, 0) 是道具占地的中心，造型向上长（负 y），
 * 尺寸按 16×11 网格的等距投影换算，保证「看起来有多大，就走不进去多大」。
 * 全部使用粗描边 + 马卡龙填充，风格与参考图一致。
 */
defineProps({
  art: { type: String, default: 'box' }
})

const INK = '#4A3F4A'
</script>

<template>
  <g class="prop-sprite">
    <!-- ============ 地毯 ============ -->
    <g v-if="art === 'rug'">
      <polygon points="0,-56 108,0 0,56 -108,0" fill="#FBD9E3" :stroke="INK" stroke-width="4.5" stroke-linejoin="round" />
      <polygon
        points="0,-42 82,0 0,42 -82,0"
        fill="#F7C6D4"
        stroke="#E79FB4"
        stroke-width="3"
        stroke-dasharray="9 9"
        stroke-linejoin="round"
      />
      <path d="M-26 -10q10-14 20 0t20 0" fill="none" stroke="#E79FB4" stroke-width="3" stroke-linecap="round" />
    </g>

    <!-- ============ 沙发 ============ -->
    <g v-else-if="art === 'sofa'">
      <ellipse cx="0" cy="4" rx="86" ry="13" fill="rgba(74,63,74,0.12)" />
      <rect x="-90" y="-60" width="180" height="48" rx="16" fill="#F7BDCA" :stroke="INK" stroke-width="5" />
      <rect x="-84" y="-102" width="168" height="58" rx="20" fill="#F2A9BC" :stroke="INK" stroke-width="5" />
      <path d="M-28-98v50M28-98v50" :stroke="INK" stroke-width="3" opacity="0.35" />
      <rect x="-96" y="-68" width="28" height="56" rx="13" fill="#EE9DB2" :stroke="INK" stroke-width="5" />
      <rect x="68" y="-68" width="28" height="56" rx="13" fill="#EE9DB2" :stroke="INK" stroke-width="5" />
      <rect x="-60" y="-54" width="52" height="32" rx="10" fill="#FBD5DE" :stroke="INK" stroke-width="3.4" />
      <rect x="8" y="-54" width="52" height="32" rx="10" fill="#FBD5DE" :stroke="INK" stroke-width="3.4" />
      <rect x="-76" y="-16" width="16" height="16" rx="5" fill="#B98A72" :stroke="INK" stroke-width="3" />
      <rect x="60" y="-16" width="16" height="16" rx="5" fill="#B98A72" :stroke="INK" stroke-width="3" />
    </g>

    <!-- ============ 书架 ============ -->
    <g v-else-if="art === 'bookshelf'">
      <ellipse cx="0" cy="4" rx="56" ry="10" fill="rgba(74,63,74,0.12)" />
      <rect x="-52" y="-152" width="104" height="152" rx="8" fill="#EBC79D" :stroke="INK" stroke-width="5" />
      <rect x="-42" y="-140" width="84" height="128" fill="#F7E4CC" :stroke="INK" stroke-width="3" />
      <g fill="none" :stroke="INK" stroke-width="3.4">
        <path d="M-42-104h84M-42-66h84M-42-28h84" />
      </g>
      <g :stroke="INK" stroke-width="2">
        <rect x="-38" y="-136" width="12" height="30" fill="#F7A8B8" />
        <rect x="-24" y="-132" width="10" height="26" fill="#9DD8C4" />
        <rect x="-12" y="-138" width="13" height="32" fill="#FBE7AE" />
        <rect x="4" y="-134" width="11" height="28" fill="#BFE3F5" />
        <rect x="18" y="-130" width="16" height="24" fill="#F6C6D2" />
        <rect x="-38" y="-98" width="14" height="30" fill="#CDEBD4" />
        <rect x="-22" y="-94" width="12" height="26" fill="#FBD7A8" />
        <rect x="-8" y="-100" width="15" height="32" fill="#C7DDF5" />
        <rect x="10" y="-96" width="12" height="28" fill="#F7B9C6" />
        <rect x="-38" y="-60" width="13" height="30" fill="#F9DCA8" />
        <rect x="-22" y="-56" width="12" height="26" fill="#A9DCC9" />
        <rect x="-6" y="-62" width="14" height="32" fill="#F5C3CF" />
      </g>
      <path d="M-30-26q10-12 20 0" fill="none" :stroke="INK" stroke-width="3" />
    </g>

    <!-- ============ 落地灯 ============ -->
    <g v-else-if="art === 'lamp'">
      <ellipse cx="0" cy="4" rx="26" ry="8" fill="rgba(74,63,74,0.12)" />
      <ellipse cx="0" cy="-2" rx="22" ry="8" fill="#E9C9A8" :stroke="INK" stroke-width="4" />
      <path d="M0-8v-96" :stroke="INK" stroke-width="5" stroke-linecap="round" />
      <path d="M-28-100h56l-12-40h-32z" fill="#FBE7AE" :stroke="INK" stroke-width="5" stroke-linejoin="round" />
      <circle cx="0" cy="-100" r="24" fill="#FFF6D3" opacity="0.5" />
      <circle cx="0" cy="-124" r="8" fill="#FFF3C4" opacity="0.8" />
    </g>

    <!-- ============ 绿植 ============ -->
    <g v-else-if="art === 'plant'">
      <ellipse cx="0" cy="4" rx="32" ry="9" fill="rgba(74,63,74,0.12)" />
      <path d="M-24-38h48l-8 38h-32z" fill="#F2AE9C" :stroke="INK" stroke-width="4.5" stroke-linejoin="round" />
      <path d="M-22-38h44" :stroke="INK" stroke-width="4" />
      <g fill="#93D2A5" :stroke="INK" stroke-width="4" stroke-linejoin="round">
        <path d="M0-40q-2-34 22-52 6 30-22 52z" />
        <path d="M0-40q2-30-24-44-2 28 24 44z" />
        <path d="M0-44q-6-30 6-46 14 20-6 46z" />
        <path d="M-2-40q-26-6-34-26 26-2 34 26z" fill="#7FC593" />
      </g>
    </g>

    <!-- ============ 茶几 ============ -->
    <g v-else-if="art === 'coffee_table'">
      <ellipse cx="0" cy="4" rx="72" ry="11" fill="rgba(74,63,74,0.12)" />
      <rect x="-62" y="-46" width="12" height="42" rx="4" fill="#D9A877" :stroke="INK" stroke-width="3.4" />
      <rect x="50" y="-46" width="12" height="42" rx="4" fill="#D9A877" :stroke="INK" stroke-width="3.4" />
      <rect x="-70" y="-64" width="140" height="22" rx="9" fill="#F3D3AD" :stroke="INK" stroke-width="5" />
      <rect x="-56" y="-20" width="112" height="8" rx="4" fill="#E9C4A0" :stroke="INK" stroke-width="3" />
    </g>

    <!-- ============ 餐桌 ============ -->
    <g v-else-if="art === 'dining_table'">
      <ellipse cx="0" cy="4" rx="78" ry="12" fill="rgba(74,63,74,0.12)" />
      <rect x="-70" y="-52" width="12" height="48" rx="4" fill="#C9926A" :stroke="INK" stroke-width="3.4" />
      <rect x="58" y="-52" width="12" height="48" rx="4" fill="#C9926A" :stroke="INK" stroke-width="3.4" />
      <rect x="-76" y="-74" width="152" height="24" rx="9" fill="#F7E2C6" :stroke="INK" stroke-width="5" />
      <path d="M-76-58h152" :stroke="INK" stroke-width="3" opacity="0.3" />
      <rect x="-30" y="-46" width="60" height="7" rx="3" fill="#EBCDAE" :stroke="INK" stroke-width="2.5" />
    </g>

    <!-- ============ 积木箱 ============ -->
    <g v-else-if="art === 'toy_box'">
      <ellipse cx="0" cy="4" rx="52" ry="10" fill="rgba(74,63,74,0.12)" />
      <rect x="-50" y="-52" width="100" height="52" rx="8" fill="#9DD8C4" :stroke="INK" stroke-width="5" />
      <rect x="-54" y="-66" width="108" height="18" rx="8" fill="#C3ECDD" :stroke="INK" stroke-width="5" />
      <path d="M-16-32h32" :stroke="INK" stroke-width="4" stroke-linecap="round" />
      <path d="M0-44l6 12 13 2-9 10 2 13-12-7-12 7 2-13-9-10 13-2z" fill="#FBE7AE" :stroke="INK" stroke-width="3" stroke-linejoin="round" />
    </g>

    <!-- ============ 拼图 ============ -->
    <g v-else-if="art === 'puzzle'">
      <rect x="-24" y="-34" width="48" height="34" rx="5" fill="#FFF8EC" :stroke="INK" stroke-width="3.6" />
      <rect x="-19" y="-29" width="18" height="13" rx="3" fill="#F7A8B8" />
      <rect x="1" y="-29" width="18" height="13" rx="3" fill="#9DD8C4" />
      <rect x="-19" y="-14" width="18" height="13" rx="3" fill="#FBE7AE" />
      <circle cx="11" cy="-7" r="7" fill="#BFE3F5" :stroke="INK" stroke-width="2.4" />
    </g>

    <!-- ============ 饼干 ============ -->
    <g v-else-if="art === 'biscuit'">
      <ellipse cx="0" cy="2" rx="17" ry="6" fill="rgba(74,63,74,0.12)" />
      <circle cx="0" cy="-17" r="16" fill="#F3D2A2" :stroke="INK" stroke-width="3.6" />
      <path d="M-9-22h3M-2-11h3M4-24h3M-6-13h3M7-14h3" :stroke="INK" stroke-width="2.6" stroke-linecap="round" />
      <path d="M12-24a8 8 0 0 1 0 12" fill="#F3D2A2" :stroke="INK" stroke-width="2.6" />
    </g>

    <!-- ============ 蜡笔 ============ -->
    <g v-else-if="art === 'crayons'">
      <ellipse cx="0" cy="2" rx="24" ry="6" fill="rgba(74,63,74,0.12)" />
      <g :stroke="INK" stroke-width="3" stroke-linejoin="round">
        <path d="M-22-4l8-14 12 6-8 14z" fill="#F7A8B8" />
        <path d="M-24-6l4-6 4 3-4 6z" fill="#FBE7AE" />
        <path d="M-4-2l6-16 12 5-6 16z" fill="#9DD8C4" />
        <path d="M-2-4l3-6 4 2-3 6z" fill="#FFF3C4" />
        <path d="M14-6l5-12 11 5-5 12z" fill="#BFE3F5" />
        <path d="M16-8l2-5 4 2-2 5z" fill="#FFF3C4" />
      </g>
    </g>

    <!-- ============ 餐盘 ============ -->
    <g v-else-if="art === 'plate'">
      <ellipse cx="0" cy="0" rx="26" ry="9" fill="#FFFFFF" :stroke="INK" stroke-width="3.6" />
      <ellipse cx="0" cy="-2" rx="18" ry="6" fill="#F3F7F4" :stroke="INK" stroke-width="2.4" />
      <g fill="#8FCF87" :stroke="INK" stroke-width="2.6" stroke-linejoin="round">
        <path d="M-11-8q6-10 12-2t-6 8q-8 0-6-6z" />
        <path d="M4-10q7-7 10 2t-8 6q-6-2-2-8z" />
      </g>
    </g>

    <!-- ============ 积木 ============ -->
    <g v-else-if="art === 'blocks'">
      <ellipse cx="0" cy="3" rx="34" ry="9" fill="rgba(74,63,74,0.12)" />
      <g :stroke="INK" stroke-width="3" stroke-linejoin="round">
        <path d="M-30-4l14-8 14 8-14 8z" fill="#F7A8B8" />
        <path d="M-30-4v-16l14-8v16z" fill="#EF94A8" />
        <path d="M-16-20l14 8v16l-14-8z" fill="#F9BDCB" />
        <path d="M2-2l14-8 14 8-14 8z" fill="#FBE7AE" />
        <path d="M2-2v-16l14-8v16z" fill="#F5D889" />
        <path d="M16-18l14 8v16l-14-8z" fill="#FCEEBE" />
        <path d="M-14-22l14-8 14 8-14 8z" fill="#BFE3F5" />
        <path d="M-14-22v-14l14-8v14z" fill="#A9D6EE" />
        <path d="M0-36l14 8v14l-14-8z" fill="#D3EEFB" />
      </g>
    </g>

    <!-- ============ 小课桌 ============ -->
    <g v-else-if="art === 'desk'">
      <ellipse cx="0" cy="4" rx="64" ry="10" fill="rgba(74,63,74,0.12)" />
      <rect x="-56" y="-30" width="10" height="30" rx="3" fill="#CDA075" :stroke="INK" stroke-width="3" />
      <rect x="46" y="-30" width="10" height="30" rx="3" fill="#CDA075" :stroke="INK" stroke-width="3" />
      <rect x="-62" y="-58" width="124" height="20" rx="8" fill="#F5D8B2" :stroke="INK" stroke-width="5" />
      <rect x="-56" y="-42" width="112" height="14" rx="4" fill="#E9C29B" :stroke="INK" stroke-width="3" />
      <rect x="-30" y="-70" width="38" height="14" rx="2" fill="#FFFFFF" :stroke="INK" stroke-width="2.6" transform="rotate(-4 -11 -63)" />
      <path d="M16-68l7 12 12 2-9 9 2 12-12-6-11 6 2-12-9-9 12-2z" fill="#FBE7AE" :stroke="INK" stroke-width="2.2" stroke-linejoin="round" />
    </g>

    <!-- ============ 讲台 ============ -->
    <g v-else-if="art === 'teacher_desk'">
      <ellipse cx="0" cy="4" rx="72" ry="11" fill="rgba(74,63,74,0.12)" />
      <rect x="-64" y="-46" width="128" height="46" rx="6" fill="#E7BE93" :stroke="INK" stroke-width="5" />
      <rect x="-42" y="-34" width="52" height="22" rx="4" fill="#D9AE82" :stroke="INK" stroke-width="3" />
      <circle cx="48" cy="-24" r="4" fill="#F6D27C" :stroke="INK" stroke-width="2.4" />
      <rect x="-70" y="-80" width="140" height="22" rx="9" fill="#F3D3AD" :stroke="INK" stroke-width="5" />
      <rect x="-46" y="-94" width="34" height="16" rx="2" fill="#FFFFFF" :stroke="INK" stroke-width="2.6" transform="rotate(-5 -29 -86)" />
      <rect x="8" y="-96" width="26" height="18" rx="3" fill="#F7C6D0" :stroke="INK" stroke-width="2.6" />
    </g>

    <!-- ============ 拼图盒 ============ -->
    <g v-else-if="art === 'puzzle_box'">
      <rect x="-24" y="-34" width="48" height="34" rx="5" fill="#BFE3F5" :stroke="INK" stroke-width="3.6" />
      <rect x="-24" y="-34" width="48" height="10" rx="4" fill="#9DD0EC" :stroke="INK" stroke-width="2.6" />
      <circle cx="-8" cy="-15" r="7" fill="#FFF8EC" :stroke="INK" stroke-width="2.4" />
      <path d="M6-22h12v12H6z" fill="#FBE7AE" :stroke="INK" stroke-width="2.4" />
    </g>

    <!-- ============ 水杯 ============ -->
    <g v-else-if="art === 'water_bottle'">
      <ellipse cx="0" cy="2" rx="12" ry="5" fill="rgba(74,63,74,0.12)" />
      <rect x="-10" y="-40" width="20" height="38" rx="7" fill="#CDE9F7" :stroke="INK" stroke-width="3.4" />
      <rect x="-8" y="-52" width="16" height="14" rx="4" fill="#8FD3C3" :stroke="INK" stroke-width="3.4" />
      <rect x="-7" y="-32" width="14" height="12" rx="3" fill="#FFFFFF" opacity="0.75" />
    </g>

    <!-- ============ 滑梯 ============ -->
    <g v-else-if="art === 'slide'">
      <ellipse cx="0" cy="4" rx="76" ry="13" fill="rgba(74,63,74,0.12)" />
      <rect x="18" y="-128" width="10" height="128" rx="4" fill="#D9A877" :stroke="INK" stroke-width="3.4" />
      <rect x="58" y="-128" width="10" height="128" rx="4" fill="#D9A877" :stroke="INK" stroke-width="3.4" />
      <g :stroke="INK" stroke-width="3">
        <path d="M18-30h50M18-58h50M18-86h50M18-114h50" />
      </g>
      <rect x="8" y="-152" width="72" height="26" rx="6" fill="#BFE3F5" :stroke="INK" stroke-width="4.5" />
      <path d="M4-152h80l-12-34H16z" fill="#F7C6D0" :stroke="INK" stroke-width="4.5" stroke-linejoin="round" />
      <path d="M20-146q-64 36-78 118l34 10q14-70 58-94z" fill="#9DD8C4" :stroke="INK" stroke-width="4.5" stroke-linejoin="round" />
      <path d="M20-146q-64 36-78 118" fill="none" stroke="#FFFFFF" stroke-width="4" opacity="0.7" />
      <path d="M-58-18l34 10" :stroke="INK" stroke-width="4" stroke-linecap="round" />
    </g>

    <!-- ============ 秋千 ============ -->
    <g v-else-if="art === 'swing'">
      <ellipse cx="0" cy="4" rx="66" ry="12" fill="rgba(74,63,74,0.12)" />
      <g :stroke="INK" stroke-width="5" stroke-linecap="round" fill="none">
        <path d="M-60 0 -24-158" stroke="#E9C29B" />
        <path d="M-60 0 10-158" stroke="#E9C29B" />
        <path d="M60 0 24-158" stroke="#E9C29B" />
        <path d="M60 0 -10-158" stroke="#E9C29B" />
        <path d="M-30-158h60" stroke="#F2A9BC" />
      </g>
      <g :stroke="INK" stroke-width="3" fill="none">
        <path d="M-14-156v94M14-156v94" />
      </g>
      <rect x="-27" y="-62" width="54" height="13" rx="6" fill="#F7C6D0" :stroke="INK" stroke-width="3.4" />
    </g>

    <!-- ============ 沙池 ============ -->
    <g v-else-if="art === 'sandbox'">
      <polygon points="0,-44 78,0 0,44 -78,0" fill="#EBC79D" :stroke="INK" stroke-width="5" stroke-linejoin="round" />
      <polygon points="0,-34 60,0 0,34 -60,0" fill="#F8E4B8" :stroke="INK" stroke-width="3" stroke-linejoin="round" />
      <g :stroke="INK" stroke-width="3">
        <path d="M-40-10h20M12-8h18M-16 16h22" stroke="#E4C89A" stroke-linecap="round" />
      </g>
      <path d="M30-40h26l-4 22H34z" fill="#9DD8C4" :stroke="INK" stroke-width="3.2" stroke-linejoin="round" />
      <path d="M30-40q13-12 26 0" fill="none" :stroke="INK" stroke-width="3" />
      <path d="M-50-30l6-18 4 2-6 18z" fill="#F7C6D0" :stroke="INK" stroke-width="2.6" />
    </g>

    <!-- ============ 长椅 ============ -->
    <g v-else-if="art === 'bench'">
      <ellipse cx="0" cy="4" rx="54" ry="9" fill="rgba(74,63,74,0.12)" />
      <rect x="-48" y="-72" width="96" height="10" rx="4" fill="#E9C29B" :stroke="INK" stroke-width="3.6" />
      <rect x="-48" y="-56" width="96" height="10" rx="4" fill="#E9C29B" :stroke="INK" stroke-width="3.6" />
      <rect x="-52" y="-40" width="104" height="16" rx="6" fill="#F3D3AD" :stroke="INK" stroke-width="4.5" />
      <rect x="-44" y="-26" width="10" height="26" rx="3" fill="#C9926A" :stroke="INK" stroke-width="3" />
      <rect x="34" y="-26" width="10" height="26" rx="3" fill="#C9926A" :stroke="INK" stroke-width="3" />
      <rect x="-52" y="-72" width="8" height="46" rx="3" fill="#C9926A" :stroke="INK" stroke-width="3" />
      <rect x="44" y="-72" width="8" height="46" rx="3" fill="#C9926A" :stroke="INK" stroke-width="3" />
    </g>

    <!-- ============ 大树 ============ -->
    <g v-else-if="art === 'tree'">
      <ellipse cx="0" cy="4" rx="44" ry="11" fill="rgba(74,63,74,0.12)" />
      <path d="M-10 0h20v-70h-20z" fill="#C9926A" :stroke="INK" stroke-width="4" />
      <path d="M0-52l-16-20M0-62l14-18" fill="none" :stroke="INK" stroke-width="4" stroke-linecap="round" />
      <g fill="#8FCF87" :stroke="INK" stroke-width="4.5">
        <circle cx="-26" cy="-104" r="30" />
        <circle cx="24" cy="-108" r="28" />
        <circle cx="0" cy="-134" r="30" />
        <circle cx="2" cy="-96" r="26" fill="#9DD89A" />
      </g>
    </g>

    <!-- ============ 皮球 ============ -->
    <g v-else-if="art === 'ball'">
      <ellipse cx="0" cy="2" rx="18" ry="6" fill="rgba(74,63,74,0.12)" />
      <circle cx="0" cy="-16" r="17" fill="#F7C6D0" :stroke="INK" stroke-width="3.6" />
      <path d="M-14-22q14 6 0 14M14-22q-14 6 0 14" fill="none" stroke="#FFFFFF" stroke-width="4" stroke-linecap="round" />
    </g>

    <!-- ============ 商店货架 ============ -->
    <g v-else-if="art === 'shelf'">
      <ellipse cx="0" cy="4" rx="62" ry="10" fill="rgba(74,63,74,0.12)" />
      <rect x="-58" y="-130" width="116" height="130" rx="6" fill="#E6EEF3" :stroke="INK" stroke-width="5" />
      <g :stroke="INK" stroke-width="3.4">
        <path d="M-58-96h116M-58-62h116M-58-30h116" />
      </g>
      <g :stroke="INK" stroke-width="2.2">
        <rect x="-50" y="-126" width="16" height="28" rx="2" fill="#F7A8B8" />
        <rect x="-30" y="-122" width="14" height="24" rx="2" fill="#FBE7AE" />
        <rect x="-12" y="-126" width="18" height="28" rx="2" fill="#BFE3F5" />
        <rect x="10" y="-120" width="14" height="22" rx="2" fill="#9DD8C4" />
        <rect x="28" y="-124" width="20" height="26" rx="2" fill="#F6C6D2" />
        <rect x="-50" y="-92" width="18" height="28" rx="2" fill="#CDEBD4" />
        <rect x="-28" y="-88" width="14" height="24" rx="2" fill="#F9D7A8" />
        <rect x="-10" y="-92" width="16" height="28" rx="2" fill="#D8E9F8" />
        <rect x="12" y="-86" width="16" height="22" rx="2" fill="#F7C6D0" />
        <rect x="-50" y="-58" width="20" height="26" rx="2" fill="#FBE7AE" />
        <rect x="-26" y="-54" width="14" height="22" rx="2" fill="#BFE3F5" />
        <rect x="-8" y="-58" width="18" height="26" rx="2" fill="#9DD8C4" />
      </g>
      <rect x="-58" y="-134" width="116" height="8" rx="4" fill="#CFDDE6" :stroke="INK" stroke-width="3" />
    </g>

    <!-- ============ 冷藏柜 ============ -->
    <g v-else-if="art === 'fridge'">
      <ellipse cx="0" cy="4" rx="60" ry="10" fill="rgba(74,63,74,0.12)" />
      <rect x="-56" y="-150" width="112" height="150" rx="10" fill="#E9F6FC" :stroke="INK" stroke-width="5" />
      <rect x="-46" y="-138" width="92" height="126" rx="6" fill="#D6EDF8" :stroke="INK" stroke-width="3.4" />
      <g :stroke="INK" stroke-width="3">
        <path d="M-46-96h92M-46-54h92" />
      </g>
      <g :stroke="INK" stroke-width="2.4">
        <rect x="-38" y="-132" width="16" height="30" rx="2" fill="#FFFFFF" />
        <rect x="-16" y="-128" width="14" height="26" rx="2" fill="#FFFFFF" />
        <rect x="4" y="-132" width="16" height="30" rx="2" fill="#FFFFFF" />
        <rect x="26" y="-126" width="14" height="24" rx="2" fill="#FFFFFF" />
        <rect x="-38" y="-90" width="16" height="30" rx="2" fill="#FFFFFF" />
        <rect x="-16" y="-86" width="14" height="26" rx="2" fill="#FFFFFF" />
        <rect x="4" y="-90" width="16" height="30" rx="2" fill="#FFFFFF" />
        <rect x="-38" y="-48" width="16" height="30" rx="2" fill="#FFFFFF" />
        <rect x="-16" y="-44" width="14" height="26" rx="2" fill="#FFFFFF" />
      </g>
      <rect x="36" y="-110" width="6" height="56" rx="3" fill="#8FA9B8" :stroke="INK" stroke-width="2.4" />
      <rect x="-56" y="-162" width="112" height="16" rx="6" fill="#9DD8C4" :stroke="INK" stroke-width="4" />
      <text x="0" y="-150" font-size="12" text-anchor="middle" fill="#3F6B58" font-weight="700">牛 奶</text>
    </g>

    <!-- ============ 收银台 ============ -->
    <g v-else-if="art === 'counter'">
      <ellipse cx="0" cy="4" rx="80" ry="12" fill="rgba(74,63,74,0.12)" />
      <rect x="-78" y="-62" width="156" height="62" rx="6" fill="#F5E3CF" :stroke="INK" stroke-width="5" />
      <path d="M-78-32h156" :stroke="INK" stroke-width="3" opacity="0.3" />
      <rect x="-84" y="-84" width="168" height="22" rx="8" fill="#FFF8EE" :stroke="INK" stroke-width="5" />
      <rect x="18" y="-124" width="46" height="40" rx="6" fill="#D8E9F8" :stroke="INK" stroke-width="3.6" />
      <rect x="26" y="-116" width="30" height="18" rx="3" fill="#BFE3F5" />
      <path d="M18-108h-14M-40-100h34" :stroke="INK" stroke-width="3" />
      <rect x="-60" y="-116" width="40" height="32" rx="4" fill="#FFFFFF" :stroke="INK" stroke-width="3" />
      <g fill="#4A3F4A">
        <rect x="-55" y="-110" width="30" height="3" />
        <rect x="-55" y="-103" width="30" height="3" />
        <rect x="-55" y="-96" width="18" height="3" />
      </g>
      <circle cx="-8" cy="-92" r="7" fill="#F6D27C" :stroke="INK" stroke-width="2.6" />
    </g>

    <!-- ============ 牛奶 ============ -->
    <g v-else-if="art === 'milk'">
      <ellipse cx="0" cy="2" rx="15" ry="5" fill="rgba(74,63,74,0.12)" />
      <path d="M-13-2h26v-34l-6-8h-14l-6 8z" fill="#FFFFFF" :stroke="INK" stroke-width="3.2" stroke-linejoin="round" />
      <path d="M-13-30l6-8h14l6 8z" fill="#EAF4FA" :stroke="INK" stroke-width="3" />
      <rect x="-13" y="-22" width="26" height="12" fill="#8FD3C3" />
      <circle cx="-4" cy="-16" r="3" fill="#FFFFFF" />
      <path d="M2-16h6M2-12h4" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round" />
    </g>

    <!-- ============ 购物篮 ============ -->
    <g v-else-if="art === 'basket'">
      <ellipse cx="0" cy="2" rx="28" ry="7" fill="rgba(74,63,74,0.12)" />
      <path d="M-26-30h52l-6 30h-40z" fill="#F7C6D0" :stroke="INK" stroke-width="3.6" stroke-linejoin="round" />
      <path d="M-18-30q18-22 36 0" fill="none" :stroke="INK" stroke-width="3.4" />
      <g :stroke="INK" stroke-width="2.2" opacity="0.6">
        <path d="M-14-28l-3 26M0-28v26M14-28l3 26" />
      </g>
    </g>

    <!-- ============ 兜底 ============ -->
    <g v-else>
      <ellipse cx="0" cy="4" rx="34" ry="9" fill="rgba(74,63,74,0.12)" />
      <rect x="-32" y="-48" width="64" height="48" rx="8" fill="#F7E4CC" :stroke="INK" stroke-width="4.5" />
      <path d="M-16-24h32" :stroke="INK" stroke-width="3.4" stroke-linecap="round" />
    </g>
  </g>
</template>
