FROM node:22-alpine AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:22-alpine AS runtime
WORKDIR /app
COPY --from=build /app/build /app/build
COPY --from=build /app/package.json /app/package.json
RUN npm install --production
EXPOSE 3000
CMD ["node", "build"]
