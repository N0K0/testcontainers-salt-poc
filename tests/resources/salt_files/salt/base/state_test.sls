cat /etc/os-release:
    cmd.run

{% for key, value in pillar.items() %}
print_pillar_{{ key }}:
  cmd.run:
    - name: echo {{ key }} {{ value }}
{% endfor %}
