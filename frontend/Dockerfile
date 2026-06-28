FROM nginx:alpine

COPY frontend/index.html /usr/share/nginx/html/index.html
COPY frontend/dashboard.css /usr/share/nginx/html/dashboard.css
COPY frontend/dashboard.js /usr/share/nginx/html/dashboard.js
COPY collections/access_logs_recent.json /usr/share/nginx/html/collections/access_logs_recent.json

EXPOSE 80
