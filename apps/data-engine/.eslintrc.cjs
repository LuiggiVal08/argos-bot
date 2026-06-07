/* eslint-env node */
module.exports = {
  root: true,
  parser: "@typescript-eslint/parser",
  parserOptions: {
    project: "./tsconfig.json",
    tsconfigRootDir: __dirname,
    sourceType: "module",
  },
  plugins: ["@typescript-eslint"],
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
  ],
  env: {
    node: true,
    es2022: true,
    jest: true,
  },
  ignorePatterns: ["dist", "node_modules", ".eslintrc.cjs"],
  rules: {
    "@typescript-eslint/no-explicit-any": "warn",
    "@typescript-eslint/no-unused-vars": [
      "error",
      { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
    ],
    "@typescript-eslint/ban-types": [
      "error",
      {
        extendDefaults: true,
        types: {
          // Our domain value-object class is named "Symbol" because
          // it represents a market symbol (e.g. "BTC/USDT"). The JS
          // built-in `Symbol` is a primitive; we accept the shadowing
          // because the domain term is more meaningful here.
          Symbol: false,
        },
      },
    ],
    "@typescript-eslint/explicit-module-boundary-types": "off",
    "no-console": ["error", { allow: ["warn", "error"] }],
    "prefer-const": "error",
    "eqeqeq": ["error", "always"],
  },
}
