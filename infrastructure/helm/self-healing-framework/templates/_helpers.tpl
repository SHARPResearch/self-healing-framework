{{/* Shared names and labels. */}}

{{- define "sharp.labels" -}}
app.kubernetes.io/part-of: sharp
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
{{- end -}}

{{- define "sharp.mlBackend.name" -}}ml-backend{{- end -}}
{{- define "sharp.timescaledb.name" -}}timescaledb{{- end -}}
{{- define "sharp.redis.name" -}}redis{{- end -}}

{{- define "sharp.selector" -}}
app.kubernetes.io/name: {{ .name }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
{{- end -}}

{{/*
TimescaleDB password: the value if set, else the one already stored in the Secret (so an upgrade
keeps it), else a new random one.
*/}}
{{- define "sharp.timescaledb.password" -}}
{{- if .Values.timescaledb.password -}}
{{- .Values.timescaledb.password -}}
{{- else -}}
{{- $existing := lookup "v1" "Secret" .Release.Namespace "timescaledb" -}}
{{- if and $existing $existing.data (index $existing.data "password") -}}
{{- index $existing.data "password" | b64dec -}}
{{- else -}}
{{- randAlphaNum 24 -}}
{{- end -}}
{{- end -}}
{{- end -}}
