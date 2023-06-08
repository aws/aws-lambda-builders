import { APIGatewayProxyEvent, APIGatewayProxyResult } from "aws-lambda";
import {axios} from "axios";
import * as requestPromise from "request-promise";


export const lambdaHandler = async (event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> => {
  const queries = JSON.stringify(event.queryStringParameters);
  return {
    statusCode: 200,
    body: "OK" 
  }
}
