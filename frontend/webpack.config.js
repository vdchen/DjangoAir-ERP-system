const path = require("path");
const webpack = require("webpack");
const { VueLoaderPlugin } = require("vue-loader");
const HtmlWebpackPlugin = require("html-webpack-plugin");
const MiniCssExtractPlugin = require("mini-css-extract-plugin");

function createSpaConfig({ name, entry, template, outputSubdir, publicPath }) {
  return {
    name,
    entry,
    output: {
      path: path.resolve(__dirname, "dist", outputSubdir),
      filename: `${name}.[contenthash:8].js`,
      publicPath,
      clean: true,
    },
    resolve: {
      extensions: [".js", ".vue", ".json"],
    },
    module: {
      rules: [
        {
          test: /\.vue$/,
          loader: "vue-loader",
        },
        {
          test: /\.css$/,
          use: [MiniCssExtractPlugin.loader, "css-loader"],
        },
      ],
    },
    plugins: [
      new VueLoaderPlugin(),
      new MiniCssExtractPlugin({
        filename: `${name}.[contenthash:8].css`,
      }),
      new HtmlWebpackPlugin({
        template,
        filename: "index.html",
      }),
      new webpack.DefinePlugin({
        __VUE_OPTIONS_API__: true,
        __VUE_PROD_DEVTOOLS__: false,
        __VUE_PROD_HYDRATION_MISMATCH_DETAILS__: false,
      }),
    ],
  };
}

module.exports = [
  createSpaConfig({
    name: "customer",
    entry: path.resolve(__dirname, "customer/main.js"),
    template: path.resolve(__dirname, "customer/index.html"),
    outputSubdir: "customer",
    publicPath: "/",
  }),
  createSpaConfig({
    name: "staff",
    entry: path.resolve(__dirname, "staff/main.js"),
    template: path.resolve(__dirname, "staff/index.html"),
    outputSubdir: "staff",
    publicPath: "/staff/",
  }),
];
