module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'scope-enum': [
      2,
      'always',
      ['app', 'backend', 'extension', 'release', 'deps'],
    ],
  },
};
