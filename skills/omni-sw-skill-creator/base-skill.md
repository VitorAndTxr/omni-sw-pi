---
model: inherit
description: descrição da skill
argument-hint: [arg1] [arg2]

context: fork
disable-model-invocation: false
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "echo 'pre-hook'"
          once: true
  PostToolUse:
    - matcher: "Edit|Write"
      hooks:
        - type: command
          command: "echo 'post-hook'"
          once: true
  Stop:
    - hooks:
      - type: command
        command: "echo 'stop-hook'"
        once: true
---
# Purpose

Descrição do propósito da skill

## Variables

Variáveis e parâmetros aceitos

## Codebase Structure

Estrutura relevante do codebase

## Instructions

Instruções de execução

## Workflow

Fluxo de trabalho

## Report

Formato do relatório/output
