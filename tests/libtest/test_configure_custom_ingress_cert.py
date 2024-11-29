from ocs_ci.framework.pytest_customization.marks import libtest
from ocs_ci.utility.ssl_certs import configure_custom_ingress_cert


@libtest
def test_configure_custom_ingress_cert():
    """
    Configure custom ingress cert

    """
    configure_custom_ingress_cert(
        skip_tls_verify=False, wait_for_machineconfigpool=True
    )
