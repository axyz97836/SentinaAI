FROM postgres:17-alpine@sha256:b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24
# Source a non-executable file inside the image; avoid host mount execute semantics.
COPY --chmod=0644 infra/postgres/init-app-role.sh /docker-entrypoint-initdb.d/10-app-role.sh
