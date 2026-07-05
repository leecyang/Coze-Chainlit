import react from '@vitejs/plugin-react-swc';
import httpProxy from 'http-proxy';
import path from 'path';
import { defineConfig } from 'vite';
import svgr from 'vite-plugin-svgr';
import tsconfigPaths from 'vite-tsconfig-paths';

const backendTarget = 'http://127.0.0.1:8000';
const buildSourcemap = process.env.VITE_BUILD_SOURCEMAP !== 'false';

const authProxy = () => {
  const proxy = httpProxy.createProxyServer({
    target: backendTarget,
    changeOrigin: true
  });

  return {
    name: 'lingxi-auth-proxy',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const pathname = req.url?.split('?')[0];
        const shouldProxy =
          (pathname === '/login' || pathname === '/logout') &&
          req.method !== 'GET';

        if (!shouldProxy) {
          next();
          return;
        }

        proxy.web(req, res, (error) => {
          next(error);
        });
      });
    }
  };
};

export default defineConfig({
  build: {
    sourcemap: buildSourcemap
  },
  server: {
    headers: {
      'Cache-Control': 'no-store'
    },
    proxy: {
      '/api': backendTarget,
      '/auth': backendTarget,
      '/config': backendTarget,
      '/feedback': backendTarget,
      '/project': backendTarget,
      '/public': backendTarget,
      '/set-session-cookie': backendTarget,
      '/user': backendTarget,
      '/v1': backendTarget,
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true
      }
    }
  },
  plugins: [authProxy(), react(), tsconfigPaths(), svgr()],
  resolve: {
    alias: {
      '@chainlit/react-client': path.resolve(
        __dirname,
        './libs/react-client/src/index.ts'
      ),
      '@': path.resolve(__dirname, './src'),
      // To prevent conflicts with packages in @chainlit/react-client, we need to specify the resolution paths for these dependencies.
      react: path.resolve(__dirname, './node_modules/react'),
      'usehooks-ts': path.resolve(__dirname, './node_modules/usehooks-ts'),
      sonner: path.resolve(__dirname, './node_modules/sonner'),
      lodash: path.resolve(__dirname, './node_modules/lodash'),
      recoil: path.resolve(__dirname, './node_modules/recoil')
    }
  }
});
