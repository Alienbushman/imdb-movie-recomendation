import withNuxt from './.nuxt/eslint.config.mjs'

export default withNuxt({
  rules: {
    'no-console': 'warn',
    'vue/multi-word-component-names': 'off',
  },
})
