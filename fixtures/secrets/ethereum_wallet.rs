// EVM / Ethereum private keys fixture

pub const OPERATOR_KEY: &str =
    "0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d";

pub fn get_signer_credentials() -> (&'static str, &'static str) {
    let private_key = "6c89f36288ced34006297063fe7e436d23157a6c62fbe75560bdec87eb232ad4";
    ("operator", private_key)
}
