// @ts-check

import { defineConfig } from "eslint/config";
import js from "@eslint/js";
import tsPlugin from "@typescript-eslint/eslint-plugin";
import tsParser from "@typescript-eslint/parser";
import security from "eslint-plugin-security";
import securityNode from "eslint-plugin-security-node";
import globals from "globals";

export default defineConfig([
  {
    files: ["**/*.{js,jsx,ts,tsx}"],

    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaVersion: "latest",
        sourceType: "module",
        project: undefined,
      },
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },

    plugins: {
      "@typescript-eslint": tsPlugin,
      security,
      "security-node": securityNode,
    },

    rules: {
      ...js.configs.recommended.rules,
      ...tsPlugin.configs.recommended.rules,

      "security/detect-object-injection": "warn",
      "security/detect-non-literal-fs-filename": "warn",
      "security-node/detect-insecure-randomness": "warn",
    },
  },
]);
