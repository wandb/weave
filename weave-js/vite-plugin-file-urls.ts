import {Plugin} from 'vite';
import fs from 'fs';

const index = fs.readFileSync(__dirname + '/index.html', 'utf-8');

const fileUrls: Plugin = {
  name: 'pass-through-file-urls',
  configureServer: server => {
    server.middlewares.use(async (req, res, next) => {
      if (req.url?.match(/.*\/artifacts\/.*\/files\/.*$/)) {
        res.write(await server.transformIndexHtml(req.url, index));
        res.end();
        return;
      }

      next();
    });
  },
};

export default fileUrls;
