export default {
  nodeResolve: true,
  files: ['tests/js/**/*.test.js'],
  testFramework: {
    config: {
      timeout: 10000,
    },
  },
};
