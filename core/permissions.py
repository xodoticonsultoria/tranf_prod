from django.contrib.auth.decorators import user_passes_test

def in_group(group_name: str):
    def check(user):
        return user.is_authenticated and user.groups.filter(name=group_name).exists()
    return user_passes_test(check)

require_austin = in_group("AUSTIN")
require_queimados = in_group("QUEIMADOS")
