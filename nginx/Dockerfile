FROM node:26-alpine AS frontend-builder

WORKDIR /frontend
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine

RUN rm -f /etc/nginx/conf.d/default.conf
COPY nginx/nginx.conf /etc/nginx/conf.d/djangoair.conf
COPY --from=frontend-builder /frontend/dist/customer /usr/share/nginx/html/customer
COPY --from=frontend-builder /frontend/dist/staff /usr/share/nginx/html/staff

EXPOSE 80
