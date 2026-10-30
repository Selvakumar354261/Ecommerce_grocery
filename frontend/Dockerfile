FROM node:22-alpine AS development
WORKDIR /web
COPY package*.json ./
RUN npm ci
COPY . .
EXPOSE 80
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "80"]
FROM development AS build
RUN npm run build
FROM nginx:1.28-alpine AS production
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /web/dist /usr/share/nginx/html
EXPOSE 80

