use lambda::lambda;
use serde_json::Value;

type Error = Box<dyn std::error::Error + Send + Sync + 'static>;

#[lambda]
#[tokio::main]
async fn main(_: Value) -> Result<Value, Error> {
    Ok("bar".into())
}