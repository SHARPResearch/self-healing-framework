# infrastructure/helm/self-healing-framework/templates/_helpers.tpl
{{/*
Common helpers used by all templates in this chart.
*/}}

{{- define "self-healing-framework.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "self-healing-framework.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "self-healing-framework.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "self-healing-framework.labels" -}}
helm.sh/chart: {{ include "self-healing-framework.chart" . }}
{{ include "self-healing-framework.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "self-healing-framework.selectorLabels" -}}
app.kubernetes.io/name: {{ include "self-healing-framework.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

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
