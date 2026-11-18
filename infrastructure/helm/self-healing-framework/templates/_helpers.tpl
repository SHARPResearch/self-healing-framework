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