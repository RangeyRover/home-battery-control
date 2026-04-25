import js from "@eslint/js";
import litPlugin from "eslint-plugin-lit";
import globals from "globals";

export default [
    js.configs.recommended,
    {
        files: ["custom_components/house_battery_control/frontend/**/*.js"],
        plugins: {
            lit: litPlugin
        },
        languageOptions: {
            ecmaVersion: 2021,
            sourceType: "module",
            globals: {
                ...globals.browser,
                customElements: "readonly"
            }
        },
        rules: {
            "no-unused-vars": "warn",
            "no-redeclare": "error",
            "no-undef": "error"
        }
    }
];
