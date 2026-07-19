import nextConfig from "eslint-config-next";

const eslintConfig = [
  ...nextConfig,
  {
    ignores: ["old/**"],
  },
];

export default eslintConfig;
