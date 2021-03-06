import React from 'react'

export default class Canvas extends React.Component {
  render() {
    return (
      <div className="row canvas">
        <div className="small-12 columns">
          {this.props.children}
        </div>
      </div>
    )
  }
}
